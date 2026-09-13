"""Read-only server compatibility checks. Does not import sys.py or load any weights."""
import ast
import sys
from pathlib import Path
from server.settings import settings


def check():
    config = settings()
    root = config['LEGACY_ROOT']
    issues = []
    path = root / config['LEGACY_MODULE']
    print(f'Legacy root: {root}')
    if not path.is_file():
        print('BLOCKED: sys.py is missing. Configure LEGACY_ROOT on the model server.')
        return 2
    tree = ast.parse(path.read_text(encoding='utf-8'))
    functions = {node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)}
    if 'process_image' not in functions:
        issues.append('process_image() missing')
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            call = node.value.func
            if isinstance(call, ast.Attribute) and call.attr == 'run':
                issues.append('Top-level .run() would block import; guard app.run with __name__ == __main__')
    assignments = {target.id for node in tree.body if isinstance(node, ast.Assign) for target in node.targets if isinstance(target, ast.Name)}
    if not assignments.intersection({'RESULT_FOLDER', 'RESULTS_FOLDER', 'OUTPUT_FOLDER'}):
        issues.append('No recognized result directory global. Inspect _save_heatmap/process_image and adapt paths first.')
    trufor_path = root / 'trufor_infer.py'
    if trufor_path.is_file():
        trufor_tree = ast.parse(trufor_path.read_text(encoding='utf-8'))
        # Accept either a module-level infer() or the real server form: a class
        # exposing infer() as a method (sys.py calls trufor_model.infer(img_pil)).
        module_level = any(isinstance(n, ast.FunctionDef) and n.name == 'infer' for n in trufor_tree.body)
        method_form = [n.name for n in trufor_tree.body
                       if isinstance(n, ast.ClassDef)
                       and any(isinstance(m, ast.FunctionDef) and m.name == 'infer' for m in n.body)]
        if module_level:
            print('OK trufor_infer.infer (module-level function)')
        elif method_form:
            print(f'OK trufor_infer infer() as method of {", ".join(method_form)} '
                  '(long-side guard is applied to the bound method)')
        else:
            issues.append('No TruFor infer() found: neither module-level infer() nor a class with an infer() method')
    else:
        issues.append('trufor_infer.py missing')
    required = ['yolo11n.pt', 'SAE_best.pth', 'SAE_v2.pth', 'mesorch-98.pth', 'mesorch_p-118.pth',
                'TruFor/TruFor_train_test/weights/trufor_ph3/best.pth.tar',
                'TruFor/TruFor_train_test/pretrained_models/noiseprint++/noiseprint++.th',
                'TruFor/TruFor_train_test/pretrained_models/segformers/mit_b2.pth',
                'TruFor/TruFor_train_test/lib/config/trufor_ph3.yaml']
    for name in required:
        file = root / name
        if not file.is_file(): issues.append(f'Missing: {name}')
        else: print(f'OK {name} ({file.stat().st_size:,} bytes)')
    if issues:
        print('\n'.join('BLOCKED: ' + item for item in issues))
        return 2
    print('Static checks passed. Next: review path rebinding and test a real image. This does not certify inference correctness.')
    return 0


if __name__ == '__main__':
    sys.exit(check())
