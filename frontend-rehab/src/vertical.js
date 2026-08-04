// Fijo por build, no configurable: este codebase (frontend-rehab/) es siempre
// el vertical médico/rehab. El original de CrossFit (frontend/) tiene su
// propio vertical.js con 'crossfit'. Login lo manda al backend, que lo
// compara contra Gimnasio.vertical — ver backend/routes/auth.py.
export const VERTICAL = 'medico'
