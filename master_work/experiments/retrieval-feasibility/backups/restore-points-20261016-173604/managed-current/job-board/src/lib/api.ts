const BASE = 'http://localhost:5000/api'

function getToken() {
  return localStorage.getItem('jb_token')
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...options.headers,
    },
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Request failed')
  return data
}

async function upload<T>(path: string, formData: FormData): Promise<T> {
  const token = getToken()
  const res = await fetch(`${BASE}${path}`, {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: formData,
  })
  const data = await res.json()
  if (!res.ok) throw new Error(data.message || 'Upload failed')
  return data
}

export const api = {
  // Auth
  register: (body: object) => request('/auth/register', { method: 'POST', body: JSON.stringify(body) }),
  login: (body: object) => request('/auth/login', { method: 'POST', body: JSON.stringify(body) }),
  me: () => request('/auth/me'),
  updateProfile: (body: object) => request('/auth/me', { method: 'PUT', body: JSON.stringify(body) }),

  // Jobs
  getJobs: (params: Record<string, string>) => {
    const qs = new URLSearchParams(params).toString()
    return request(`/jobs?${qs}`)
  },
  getFeaturedJobs: () => request('/jobs/featured'),
  getJob: (id: string) => request(`/jobs/${id}`),
  getMyJobs: () => request('/jobs/employer/mine'),
  createJob: (body: object) => request('/jobs', { method: 'POST', body: JSON.stringify(body) }),
  updateJob: (id: string, body: object) => request(`/jobs/${id}`, { method: 'PUT', body: JSON.stringify(body) }),
  deleteJob: (id: string) => request(`/jobs/${id}`, { method: 'DELETE' }),

  // Applications
  apply: (formData: FormData) => upload('/applications', formData),
  getMyApplications: () => request('/applications/mine'),
  getJobApplications: (jobId: string) => request(`/applications/job/${jobId}`),
  getEmployerApplications: () => request('/applications/employer'),
  updateApplicationStatus: (id: string, status: string) =>
    request(`/applications/${id}/status`, { method: 'PATCH', body: JSON.stringify({ status }) }),
}
