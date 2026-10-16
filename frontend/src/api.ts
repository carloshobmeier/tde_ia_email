let token = '';
export function setToken(value: string) { token = value; }
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (token) headers.set('X-Foco-Token', token);
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  const response = await fetch(`/api${path}`, { ...options, headers });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = typeof data.detail === 'string' ? data.detail : 'Não foi possível concluir. Confira os campos e tente novamente.';
    throw new Error(detail);
  }
  return response.json();
}
export const post = <T,>(path: string, data?: unknown) => api<T>(path, { method: 'POST', body: data ? JSON.stringify(data) : undefined });
export const patch = <T,>(path: string, data: unknown) => api<T>(path, { method: 'PATCH', body: JSON.stringify(data) });
export const categoryNames: Record<string, string> = { faculdade: 'Faculdade', trabalho: 'Trabalho', financeiro: 'Financeiro', pessoal: 'Pessoal', promocoes: 'Promoções' };
export const priorityNames: Record<string, string> = { urgente: 'Alta prioridade', normal: 'Normal', baixa: 'Baixa prioridade' };
export function dateLabel(value: string, time = false) { return new Intl.DateTimeFormat('pt-BR', { day: '2-digit', month: 'short', ...(time ? { hour: '2-digit', minute: '2-digit' } as const : {}) }).format(new Date(value)); }
export function shortDate(value: string) {
  const date = new Date(value), today = new Date();
  if (date.toDateString() === today.toDateString()) return date.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' });
  return date.toLocaleDateString('pt-BR', { day: '2-digit', month: 'short' });
}
export function initials(name: string) { return name.replace(/^(Prof\.?ª?\s*)/i, '').split(' ').filter(Boolean).slice(0, 2).map(s => s[0]).join('').toUpperCase(); }
