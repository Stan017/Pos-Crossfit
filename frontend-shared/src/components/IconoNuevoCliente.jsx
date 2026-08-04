export default function IconoNuevoCliente({ size = 28 }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 100 100"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      {/* Cuerpo del usuario */}
      <circle cx="42" cy="32" r="18" stroke="currentColor" strokeWidth="7" fill="none" />
      <path
        d="M8 88c0-18.78 15.22-34 34-34s34 15.22 34 34"
        stroke="currentColor"
        strokeWidth="7"
        strokeLinecap="round"
        fill="none"
      />
      {/* Badge "+" — fondo blanco con borde suave */}
      <rect x="62" y="10" width="32" height="32" rx="8" fill="white" />
      {/* Cruz roja */}
      <line x1="78" y1="18" x2="78" y2="34" stroke="#e05555" strokeWidth="5.5" strokeLinecap="round" />
      <line x1="70" y1="26" x2="86" y2="26" stroke="#e05555" strokeWidth="5.5" strokeLinecap="round" />
    </svg>
  )
}
