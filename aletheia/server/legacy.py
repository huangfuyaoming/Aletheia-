"""Adapter for the existing server's sys.py. Never substitutes SAE.py or new weights."""
import importlib.util
import math
import re
import sys
import threading
import time
from pathlib import Path


class InferenceUnavailable(RuntimeError):
    pass


class LegacyPipeline:
    def __init__(self, config):
        self.config = config
        self.module = None
        self.lock = threading.Lock()
        self.state = 'not_loaded'

    def health(self):
        exists = (self.config['LEGACY_ROOT'] / self.config['LEGACY_MODULE']).is_file()
        return {'available': exists, 'state': self.state if exists else 'not_configured',
                'device': str(getattr(self.module, 'device', 'not_loaded')),
                'mode': 'legacy', 'message': '模型将在首次鉴别时加载' if exists else '尚未连接服务器模型'}

    def _load(self):
        if self.module:
            return self.module
        root = self.config['LEGACY_ROOT']
        path = root / self.config['LEGACY_MODULE']
        if not path.is_file():
            raise InferenceUnavailable('尚未连接服务器模型，请完成服务器配置后再鉴别。')
        self.state = 'loading'
        sys.path.insert(0, str(root))
        spec = importlib.util.spec_from_file_location('aletheia_legacy_sys', path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
            if not callable(getattr(module, 'process_image', None)):
                raise InferenceUnavailable('服务器未提供 process_image 接口。')
            # Preserve all architecture/checkpoint logic; fix inference mode only.
            # Use a real isinstance check: duck-typing on hasattr() touches werkzeug
            # LocalProxy globals (request/session) imported by sys.py, which raise
            # "Working outside of request context" during attribute access.
            import torch.nn as nn
            for value in list(vars(module).values()):
                if isinstance(value, nn.Module):
                    value.eval()
            self._limit_trufor(module)
            self.module = module
            self.state = 'ready'
            return module
        except Exception:
            self.state = 'error'
            sys.modules.pop(spec.name, None)
            raise

    def _limit_trufor(self, module):
        """Wrap only TruFor, keeping SAE/Mesorch preprocessing completely intact.

        The server's real interface is the bound method `TruForInfer.infer(image)`,
        called as `trufor_model.infer(img_pil)` in sys.py, not a module-level
        `trufor_infer.infer`. The long-side guard is applied at that real call site;
        it is never silently skipped.
        """
        max_side = self.config['TRUFOR_MAX_SIDE']
        # Check the concrete type BEFORE any getattr: werkzeug LocalProxy globals
        # (request/session) raise on attribute access outside a request context.
        targets = [(module, name, value)
                   for name, value in list(vars(module).items())
                   if type(value).__name__ == 'TruForInfer' and callable(getattr(value, 'infer', None))]
        module_level = sys.modules.get('trufor_infer')
        if module_level is not None and callable(getattr(module_level, 'infer', None)):
            targets.append((module_level, 'infer', module_level))
        if not targets:
            if getattr(module, 'trufor_model', 'missing') is None:
                return  # Legacy pipeline already flagged TruFor unavailable; 4-model degrade applies.
            raise InferenceUnavailable('未找到 TruFor 推理接口（既无 TruForInfer.infer 实例也无模块级 infer），'
                                       '请按服务器交接文档确认接口。')

        def wrap(original):
            def bounded(image, *args, **kwargs):
                from PIL import Image
                import cv2
                size = image.size
                limited = image.copy()
                limited.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
                score, loc, conf = original(limited, *args, **kwargs)
                if limited.size != size:
                    loc = cv2.resize(loc, size)
                    if conf is not None:
                        conf = cv2.resize(conf, size)
                return score, loc, conf
            return bounded

        for owner, name, holder in targets:
            if holder is owner and name == 'infer':
                owner.infer = wrap(owner.infer)          # module-level function form
            else:
                holder.infer = wrap(holder.infer)        # bound-method form (real server)

    def run(self, input_path, output_dir):
        with self.lock:
            module = self._load()
            output_dir = Path(output_dir).resolve()
            output_dir.mkdir(parents=True, exist_ok=True)
            # Known globals are rebound for this serialized task. The legacy Flask app is never served.
            for name in ('RESULT_FOLDER', 'RESULTS_FOLDER', 'OUTPUT_FOLDER'):
                if hasattr(module, name):
                    setattr(module, name, str(output_dir))
            for name in ('UPLOAD_FOLDER',):
                if hasattr(module, name):
                    setattr(module, name, str(Path(input_path).parent))
            if hasattr(module, 'app'):
                for name in ('RESULT_FOLDER', 'RESULTS_FOLDER', 'OUTPUT_FOLDER'):
                    module.app.config[name] = str(output_dir)
                module.app.config['UPLOAD_FOLDER'] = str(Path(input_path).parent)
            start = time.monotonic()
            context = module.process_image(str(input_path), Path(input_path).name)
            return normalize_result(context, output_dir, round((time.monotonic() - start) * 1000))


def probability(value):
    if value is None or value == '—':
        return None
    try:
        if isinstance(value, str) and value.endswith('%'):
            value = float(value[:-1]) / 100
        value = float(value)
        return value if math.isfinite(value) and 0 <= value <= 1 else None
    except (TypeError, ValueError):
        return None


def normalize_result(ctx, output_dir, elapsed_ms):
    if not isinstance(ctx, dict) or type(ctx.get('is_fake_bool')) is not bool:
        raise ValueError('Legacy response missing is_fake_bool')
    fields = {'sae_v1': 'conf_v1', 'sae_v2': 'conf_v2', 'mesorch': 'conf_meso',
              'mesorch_p': 'conf_meso_p', 'trufor': 'conf_trufor'}
    raw = ctx.get('scores', {})
    scores = {model: probability(raw.get(model, ctx.get(key))) for model, key in fields.items()}
    artifacts = []
    keys = {'yolo_res': ('yolo', 'yolo'), 'heat_v1': ('heatmap', 'sae_v1'), 'mask_v1': ('mask', 'sae_v1'),
            'heat_v2': ('heatmap', 'sae_v2'), 'mask_v2': ('mask', 'sae_v2'),
            'heat_meso': ('heatmap', 'mesorch'), 'mask_meso': ('mask', 'mesorch'),
            'heat_meso_p': ('heatmap', 'mesorch_p'), 'mask_meso_p': ('mask', 'mesorch_p'),
            'trufor_res': ('heatmap', 'trufor'), 'trufor_mask': ('mask', 'trufor')}
    for key, (kind, model) in keys.items():
        if not ctx.get(key):
            continue
        path = (output_dir / Path(ctx[key]).name).resolve()
        if not path.is_relative_to(output_dir) or not path.is_file():
            raise ValueError(f'Legacy artifact not written to private task directory: {key}')
        artifacts.append({'path': path, 'kind': kind, 'model': model})
    if not any(a['kind'] == 'heatmap' for a in artifacts):
        raise ValueError('Legacy response contains no heatmap')
    # Legacy logic_info states fake votes when flagged ("高风险：4/5 个模型判定为篡改")
    # but REAL votes otherwise ("低风险：5/5 个模型判定为真实"). Reading the digits
    # blindly would report real votes as fake ones.
    info = ctx.get('logic_info', '')
    votes = re.search(r'(\d+)\s*/\s*(\d+)', info)
    vote_counts = None
    if votes:
        counted, total = int(votes[1]), int(votes[2])
        if 0 <= counted <= total:
            fake = counted if '篡改' in info else total - counted
            vote_counts = {'fake': fake, 'total': total}
    return {'is_fake': ctx['is_fake_bool'], 'scores': scores,
            'votes': vote_counts,
            'elapsed_ms': elapsed_ms, 'degraded': scores['trufor'] is None,
            'score_semantics': 'fake_probability', 'calibrated': False,
            'pipeline_version': 'legacy-v5.0-adapter-1', 'artifacts': artifacts,
            'limitations': ['mesorch_center_crop', 'uncalibrated_scores'] + (['sae_v1_score_missing'] if scores['sae_v1'] is None else [])}
