// Validaciones del formulario de alta. Son las mismas reglas que aplica la API (src/utils/validaciones.py);
// acá se usan para avisar enseguida, y la API además revisa que el dominio del correo exista.

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$/;
const PREFIJOS_CUIT = ["20", "23", "24", "27", "30", "33", "34"];
const PESOS_CUIT = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2];
const NOMBRE_RE = /^[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'´ .-]*$/;

/** Devuelve el mensaje de error, o null si el valor es válido. */
export function errorEmail(v: string): string | null {
  const s = v.trim();
  if (!s) return "Ingresá tu correo electrónico";
  if (!EMAIL_RE.test(s) || s.length > 254) return "Ingresá un correo válido, por ejemplo nombre@gmail.com";
  return null;
}

export function soloDigitosCuit(v: string): string {
  return v.replace(/\D/g, "").slice(0, 11);
}

/** 20123456789 → 20-12345678-9 (se va armando mientras se escribe). */
export function formatoCuit(v: string): string {
  const d = soloDigitosCuit(v);
  if (d.length <= 2) return d;
  if (d.length <= 10) return `${d.slice(0, 2)}-${d.slice(2)}`;
  return `${d.slice(0, 2)}-${d.slice(2, 10)}-${d.slice(10)}`;
}

export function errorCuit(v: string): string | null {
  const d = v.replace(/[-\s.]/g, "");
  if (!d) return "Ingresá tu CUIT";
  if (!/^\d{11}$/.test(d)) return "El CUIT tiene que tener 11 dígitos";
  if (!PREFIJOS_CUIT.includes(d.slice(0, 2))) return "El CUIT no es válido: tiene que empezar con 20, 23, 24, 27, 30, 33 o 34";
  const resto = 11 - (PESOS_CUIT.reduce((s, p, i) => s + p * Number(d[i]), 0) % 11);
  const dv = resto === 11 ? 0 : resto === 10 ? -1 : resto;
  if (dv !== Number(d[10])) return "El CUIT no es válido: revisá los números (el dígito verificador no coincide)";
  return null;
}

export function errorNombre(v: string): string | null {
  const s = v.trim().replace(/\s+/g, " ");
  if (!s) return "Ingresá tu nombre y apellido";
  if (s.length > 120) return "El nombre puede tener hasta 120 caracteres";
  if (!NOMBRE_RE.test(s)) return "El nombre solo puede tener letras y espacios";
  if (s.split(" ").length < 2) return "Ingresá nombre y apellido";
  return null;
}

export function errorPassword(v: string): string | null {
  if (!v) return "Creá una contraseña";
  if (v.length < 8) return "La contraseña tiene que tener al menos 8 caracteres";
  if (v.length > 128) return "La contraseña puede tener hasta 128 caracteres";
  if (v.trim() !== v) return "La contraseña no puede empezar ni terminar con espacios";
  return null;
}
