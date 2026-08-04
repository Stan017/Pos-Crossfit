// Fijo por build, no configurable: este codebase (frontend/) es siempre el
// vertical CrossFit. El fork médico/rehab (frontend-rehab/) tiene su propio
// vertical.js con 'medico'. Login lo manda al backend, que lo compara contra
// Gimnasio.vertical — ver backend/routes/auth.py.
export const VERTICAL = 'crossfit'
