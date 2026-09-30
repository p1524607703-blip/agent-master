export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000/api'
export const AUTH_TOKEN_KEY = 'adsight_access_token'

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem(AUTH_TOKEN_KEY)
  return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function getJsonStrict<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, { headers: authHeaders() })
  if (!response.ok) throw new Error(`数据读取失败（${response.status}）`)
  return await response.json() as T
}

export async function getJson<T>(path: string, fallback: T): Promise<T> {
  try {
    return await getJsonStrict<T>(path)
  } catch {
    return fallback
  }
}

export async function postBinary<T>(path: string, body: Blob, headers: Record<string,string>, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type':'application/octet-stream', ...authHeaders(), ...headers },
      body,
    })
    if (!response.ok) throw new Error(String(response.status))
    return await response.json() as T
  } catch {
    return fallback
  }
}

export async function postEmpty<T>(path: string, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, { method:'POST', headers: authHeaders() })
    if (!response.ok) throw new Error(String(response.status))
    return await response.json() as T
  } catch {
    return fallback
  }
}

export async function postJson<T>(path: string, body: unknown, fallback: T): Promise<T> {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type':'application/json', ...authHeaders() },
      body: JSON.stringify(body),
    })
    if (!response.ok) throw new Error(String(response.status))
    return await response.json() as T
  } catch {
    return fallback
  }
}
