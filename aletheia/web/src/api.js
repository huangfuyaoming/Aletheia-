let csrf = '';
let sessionPromise;

export class ApiError extends Error {
  constructor(message, code, status) { super(message); this.code = code; this.status = status; }
}

export async function api(path, options = {}) {
  const { json, ...rest } = options;
  let response;
  try {
    response = await fetch(`/api/v1${path}`, {
      ...rest, credentials: 'same-origin',
      headers: { ...(json !== undefined ? { 'Content-Type': 'application/json' } : {}),
        ...(csrf ? { 'X-CSRF-Token': csrf } : {}), ...rest.headers },
      ...(json !== undefined ? { body: JSON.stringify(json) } : {}),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError('暂时无法连接服务，请稍后重试。', 'NETWORK_ERROR', 0);
  }
  if (response.status === 204) return null;
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(data?.error?.message || '服务暂时不可用。', data?.error?.code, response.status);
  if (!data) throw new ApiError('服务返回了无法识别的内容。', 'INVALID_RESPONSE', response.status);
  return data;
}

export function initSession() {
  if (!sessionPromise) sessionPromise = api('/session').then(data => { csrf = data.csrf_token; return data; })
    .catch(error => { sessionPromise = null; throw error; });
  return sessionPromise;
}

export function uploadImage(file, onProgress, signal) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', '/api/v1/detect');
    xhr.setRequestHeader('X-CSRF-Token', csrf);
    xhr.upload.onprogress = event => { if (event.lengthComputable) onProgress(Math.round(event.loaded / event.total * 100)); };
    xhr.onload = () => {
      signal?.removeEventListener('abort', abort);
      let data; try { data = JSON.parse(xhr.responseText); } catch { reject(new Error('服务返回了无法识别的内容。')); return; }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data);
      else reject(new ApiError(data?.error?.message || '图片上传失败。', data?.error?.code, xhr.status));
    };
    xhr.onerror = () => reject(new Error('上传连接中断，请重试。'));
    xhr.onabort = () => reject(new DOMException('上传已取消', 'AbortError'));
    const abort = () => xhr.abort();
    signal?.addEventListener('abort', abort, { once: true });
    const form = new FormData(); form.append('file', file); xhr.send(form);
  });
}

export const modelNames = { sae_v1: 'SAEv1', sae_v2: 'SAEv2', mesorch: 'Mesorch', mesorch_p: 'MesorchP', trufor: 'TruFor' };
export const statuses = { queued: '等待鉴别', running: '正在鉴别', completed: '鉴别完成', failed: '未能完成' };
export const formatDate = value => new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }).format(new Date(value));
