import { useEffect, useRef, type ReactNode } from 'react';
import { ArrowUpRight, Check, LoaderCircle, Mail, Sparkles, X } from 'lucide-react';
import type { Mail as Message, Priority } from './types';
import { categoryNames, dateLabel, initials } from './api';

export function Logo({ small = false }: { small?: boolean }) {
  return <div className={`brand ${small ? 'small' : ''}`}><span className="brand-mark"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="M10 28V15c0-7 5-10 14-8v6c-5-1-7 0-7 4h8v6h-8v5z" fill="currentColor" /></svg></span>{!small && <span>foco<span className="brand-period">.</span></span>}</div>;
}
export function ProviderIcon({ provider }: { provider: string }) {
  return <span className={`provider-icon ${provider}`} aria-label={provider === 'gmail' ? 'Gmail' : provider === 'outlook' ? 'Outlook' : 'Arquivos locais'}>{provider === 'gmail' ? <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 19V6l9 7 9-7v13" fill="none" stroke="#d97766" strokeWidth="3.5" strokeLinejoin="round"/><path d="m3 6 9 7 9-7" fill="none" stroke="#c45248" strokeWidth="3.5"/></svg> : provider === 'outlook' ? <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="8" y="4" width="14" height="17" rx="2" fill="#88abdc"/><path d="m9 9 6 5 7-5" fill="none" stroke="#fff" strokeWidth="1.4"/><rect x="1" y="6" width="13" height="14" rx="2" fill="#477cb8"/><ellipse cx="7.5" cy="13" rx="3" ry="4" fill="none" stroke="#fff" strokeWidth="1.5"/></svg> : <Mail size={20} />}</span>;
}
export function PriorityBadge({ priority }: { priority: Priority }) {
  return <span className={`priority-badge ${priority}`}><i />{priority === 'urgente' ? 'Prioridade alta' : priority === 'normal' ? 'Normal' : 'Sem pressa'}</span>;
}
export function Avatar({ name, category, size = '' }: { name: string; category: string; size?: string }) {
  return <span className={`avatar ${category} ${size}`}>{initials(name)}</span>;
}
export function EmptyState({ title, description, children, icon }: { title: string; description: string; children?: ReactNode; icon?: ReactNode }) {
  return <div className="empty-state"><div className="empty-symbol">{icon || <Mail size={30} strokeWidth={1.3} />}</div><h3>{title}</h3><p>{description}</p>{children}</div>;
}
export function Spinner({ label = 'Carregando' }: { label?: string }) { return <span className="spinner-label"><LoaderCircle size={17} className="spin" />{label}</span>; }
export function useDialog(onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose); close.current = onClose;
  useEffect(() => {
    const previous = document.activeElement as HTMLElement | null;
    const selector = 'button:not([disabled]),a[href],input,select,textarea,[tabindex="0"]';
    const panel = ref.current;
    const first = panel?.querySelector<HTMLElement>(selector); first?.focus();
    const old = document.body.style.overflow; document.body.style.overflow = 'hidden';
    function key(event: KeyboardEvent) {
      if (event.key === 'Escape') { event.preventDefault(); close.current(); }
      if (event.key === 'Tab' && panel) {
        const items = Array.from(panel.querySelectorAll<HTMLElement>(selector)).filter(e => e.offsetParent !== null);
        const start = items[0], end = items[items.length - 1];
        if (event.shiftKey && document.activeElement === start) { event.preventDefault(); end?.focus(); }
        else if (!event.shiftKey && document.activeElement === end) { event.preventDefault(); start?.focus(); }
      }
    }
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('keydown', key); document.body.style.overflow = old; previous?.focus(); };
  }, []);
  return ref;
}
export function Modal({ title, description, children, onClose }: { title: string; description?: string; children: ReactNode; onClose: () => void }) {
  const ref = useDialog(onClose);
  return <div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><div className="modal" ref={ref} role="dialog" aria-modal="true" aria-label={title}><button className="icon-button modal-close" onClick={onClose} aria-label="Fechar"><X size={20} /></button><h2>{title}</h2>{description && <p className="muted">{description}</p>}{children}</div></div>;
}
export function FocusCard({ message, onOpen, onDone }: { message: Message; onOpen: () => void; onDone: () => void }) {
  const analysis = message.analysis;
  return <article className={`focus-card ${message.category}`}>
    <div className="focus-card-top"><span className={`category-label ${message.category}`}>{categoryNames[message.category]}</span><button className="icon-button" onClick={onDone} title="Concluir ação" aria-label={`Concluir: ${analysis?.action || message.subject}`}><Check size={17} /></button></div>
    <button className="focus-card-body" onClick={onOpen}><h3>{analysis?.action || message.subject}</h3><p>{analysis?.summary || message.preview}</p></button>
    <div className="focus-card-footer"><span>{analysis?.due_at ? <><span className="due-dot" />{dateLabel(analysis.due_at)}{!analysis.due_confirmed && <span title="Prazo sugerido; confira o e-mail"> · sugerido</span>}</> : 'Sem prazo definido'}</span><button className="round-arrow" onClick={onOpen} aria-label={`Abrir ${message.subject}`}><ArrowUpRight size={17} /></button></div>
  </article>;
}
export function LocalBadge({ ready }: { ready: boolean }) { return <span className={`local-badge ${ready ? 'ready' : ''}`}><Sparkles size={13} />{ready ? 'IA no seu computador' : 'Seu espaço local'}</span>; }
