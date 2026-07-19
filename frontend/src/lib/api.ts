import type { Approval, CaseDetail, CaseSummary, Page } from '../types'
const API = import.meta.env.VITE_API_URL ?? `http://${window.location.hostname}:8000/api/v1`
let demoUser = 'user-coordinator'
export const setDemoUser = (value:string) => { demoUser = value }
async function request<T>(path:string, init?:RequestInit):Promise<T>{
  const response = await fetch(`${API}${path}`, { ...init, headers: {'Content-Type':'application/json','X-Demo-User-ID':demoUser,...init?.headers} })
  if(!response.ok){ const data = await response.json().catch(()=>({message:response.statusText})); throw new Error(data.message ?? data.detail ?? 'Request failed') }
  return response.json() as Promise<T>
}
export const api = {
  cases: (query='') => request<Page<CaseSummary>>(`/cases${query}`),
  case: (id:string) => request<CaseDetail>(`/cases/${id}`),
  approvals: () => request<Approval[]>('/approvals'),
  audit: (id:string) => request<Array<Record<string,unknown>>>(`/cases/${id}/audit`),
  kpis: () => request<Record<string,unknown>>('/kpis'),
  users: () => request<Array<{id:string;name:string;role:string}>>('/users'),
  decide: (id:string,decision:string,rationale:string) => request<{status:string;approval_token?:string}>(`/approvals/${id}/decisions`,{method:'POST',body:JSON.stringify({decision,rationale})}),
  replay: (scenario_key:string) => request<{case_id:string}>('/demo/replay',{method:'POST',body:JSON.stringify({scenario_key})}),
}
