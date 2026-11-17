// Catch incomplete published files before npm reports a generic EUSAGE error.
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const frontend = process.argv[2] || fileURLToPath(new URL("../frontend/", import.meta.url));
const lockPath = path.join(frontend, "package-lock.json");

try {
  const lock = JSON.parse(readFileSync(lockPath, "utf8").replace(/^\uFEFF/, ""));
  if (!lock || !Number.isInteger(lock.lockfileVersion) || lock.lockfileVersion < 1) {
    throw new Error("lockfileVersion debe ser un entero mayor o igual a 1");
  }
  if (lock.lockfileVersion >= 2 && (!lock.packages || !lock.packages[""])) {
    throw new Error("faltan los datos del proyecto en packages");
  }
  console.log("Dependencias: package-lock.json valido.");
} catch (error) {
  console.error("No se puede compilar: frontend/package-lock.json falta o esta incompleto/invalido.");
  console.error(`Archivo: ${lockPath}`);
  console.error(`Detalle: ${error.message}`);
  console.error("Recupera la copia completa del archivo desde PilotoAzure y vuelve a ejecutar ACTUALIZAR_INTERFAZ.cmd.");
  process.exitCode = 1;
}
