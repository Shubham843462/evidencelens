export const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function readError(response) {
  try {
    const data = await response.json()
    return typeof data.detail === 'string' ? data.detail : `Request failed (${response.status})`
  } catch {
    return `Request failed (${response.status})`
  }
}

export async function getJson(path) {
  const response = await fetch(`${API}${path}`)
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function postJson(path, payload) {
  const response = await fetch(`${API}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}

export async function uploadVideo(file, task) {
  const form = new FormData()
  form.append('file', file)
  form.append('task', task || '')
  const response = await fetch(`${API}/api/videos`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await readError(response))
  return response.json()
}
