import threading
import time
import random
import statistics

class PuenteEquitativo:
    def __init__(self):
        self._condition       = threading.Condition()
        self._direction       = None  # Sentido actual (None = libre)
        self._en_puente       = 0     # Vehículos cruzando ahora
        self._esperando       = {"NORTE": 0, "SUR": 0}  # En cola de espera

        # Monitoreo interno (protegido por el mismo lock)
        self._norte_en_puente = 0
        self._sur_en_puente   = 0

        # Métricas recolectadas para el Frente 5
        self.total_cruzados   = {"NORTE": 0, "SUR": 0}
        self.tiempos_espera   = {"NORTE": [], "SUR": []}
        self.max_simultaneos  = 0
        self.violaciones      = 0

    # ── INVARIANTE EJECUTABLE ────────────────────────────────────
    def _verificar_invariante(self):
        ok = not (self._norte_en_puente > 0 and self._sur_en_puente > 0)
        if not ok:
            self.violaciones += 1
        assert ok, (
            f"¡INVARIANTE VIOLADO! "
            f"Norte={self._norte_en_puente}, Sur={self._sur_en_puente}"
        )

    # ── CONDICIÓN DE ENTRADA (política de equidad) ───────────────
    def _puede_entrar(self, direction):
    
        contrario = "SUR" if direction == "NORTE" else "NORTE"

        if self._direction is None:
            return True

        if self._direction != direction:
            return False   # Puente ocupado por el contrario

        if self._esperando[contrario] > 0:
            return False   # Cede el paso

        return True

    # ── ENTRADA AL PUENTE ────────────────────────────────────────
    def entrar(self, vid, direction):
        """
        Solicita entrar. Bloquea si no se cumple la condición de equidad.
        """
        t_llegada = time.time()

        with self._condition:
            self._esperando[direction] += 1

            while not self._puede_entrar(direction):
                self._condition.wait()

            self._esperando[direction] -= 1
            self._direction = direction
            self._en_puente += 1

            if direction == "NORTE":
                self._norte_en_puente += 1
            else:
                self._sur_en_puente += 1

            self._verificar_invariante()

            if self._en_puente > self.max_simultaneos:
                self.max_simultaneos = self._en_puente

        t_espera = time.time() - t_llegada
        # Guardamos fuera del lock para no bloquear a otros
        with self._condition:
            self.tiempos_espera[direction].append(t_espera)

    # ── SALIDA DEL PUENTE ────────────────────────────────────────
    def salir(self, vid, direction):
        """
        Sale del puente. Si es el último, libera el sentido y notifica.
        """
        with self._condition:
            self._en_puente -= 1
            if direction == "NORTE":
                self._norte_en_puente -= 1
            else:
                self._sur_en_puente -= 1
            self.total_cruzados[direction] += 1

            if self._en_puente == 0:
                self._direction = None
                self._condition.notify_all()

    # ── REPORTE DE MÉTRICAS ──────────────────────────────────────
    def reporte(self):
        print()
        for d in ("NORTE", "SUR"):
            tiempos = self.tiempos_espera[d]
            if tiempos:
                print(f"  {d:<5}: cruzados={self.total_cruzados[d]:>3} | "
                      f"espera_prom={statistics.mean(tiempos)*1000:.1f}ms | "
                      f"espera_max={max(tiempos)*1000:.1f}ms | "
                      f"espera_min={min(tiempos)*1000:.1f}ms")
        print(f"  Máximo simultáneo en puente : {self.max_simultaneos}")
        print(f"  Violaciones de invariante   : {self.violaciones}")


# ── FUNCIÓN DE VEHÍCULO ──────────────────────────────────────────
def vehiculo(vid, direction, puente, tiempo_cruce=0.05):
    puente.entrar(vid, direction)
    time.sleep(tiempo_cruce)
    puente.salir(vid, direction)


# ── PRUEBA NORMAL ────────────────────────────────────────────────
def prueba_normal():
    print("── Prueba normal: 20 Norte + 20 Sur aleatorios ──────")
    puente = PuenteEquitativo()
    hilos  = []

    for i in range(20):
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i,      "NORTE", puente, random.uniform(0.02, 0.06))))
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i + 20, "SUR",   puente, random.uniform(0.02, 0.06))))

    random.shuffle(hilos)
    for h in hilos:
        h.start()
        time.sleep(random.uniform(0, 0.005))
    for h in hilos:
        h.join()

    puente.reporte()


# ── CARGA ADVERSA (demuestra equidad) ────────────────────────────
def prueba_carga_adversa():

    print()
    print("── Carga adversa: Norte continuo vs Sur esporádico ──")
    puente = PuenteEquitativo()

    resultados_sur  = []   # (vid, tiempo_espera)
    activo          = True

    def generador_norte():
        """Inyecta vehículos del norte sin parar mientras activo=True."""
        vid = 0
        while activo:
            t = threading.Thread(
                target=vehiculo,
                args=(vid, "NORTE", puente, 0.03))
            t.start()
            time.sleep(0.01)   # Un vehículo norte cada 10 ms
            vid += 1

    def vehiculo_sur_mide(vid):
        t0 = time.time()
        puente.entrar(vid, "SUR")
        espera = time.time() - t0
        resultados_sur.append((vid, espera))
        time.sleep(0.03)
        puente.salir(vid, "SUR")

    gen = threading.Thread(target=generador_norte)
    gen.start()

    time.sleep(0.1)  # Deja que el norte tome el puente

    hilos_sur = []
    for i in range(10):
        h = threading.Thread(target=vehiculo_sur_mide, args=(i,))
        hilos_sur.append(h)
        h.start()
        time.sleep(0.1)   # Un vehículo sur cada 100 ms

    for h in hilos_sur:
        h.join()

    activo = False
    gen.join(timeout=2)

    print(f"  {'VID':>4}  {'Espera (ms)':>12}")
    print(f"  {'----':>4}  {'----------':>12}")
    for vid, espera in resultados_sur:
        print(f"  {vid:>4}  {espera*1000:>11.1f}ms")

    max_espera = max(e for _, e in resultados_sur)
    print()
    print(f"  Espera máxima SUR: {max_espera*1000:.1f} ms")
    print(f"  Todos los del SUR cruzaron: "
          f"{'SÍ ' if len(resultados_sur) == 10 else 'NO '}")


# ── PRUEBA DE ESTRÉS ─────────────────────────────────────────────
def prueba_estres():
    print()
    print("── Prueba de estrés: 50 Norte + 50 Sur simultáneos ──")
    puente = PuenteEquitativo()
    barrier = threading.Barrier(100)

    def vehiculo_estres(vid, direction):
        barrier.wait()   # Todos arrancan al mismo tiempo
        vehiculo(vid, direction, puente, random.uniform(0.01, 0.04))

    hilos = []
    for i in range(50):
        hilos.append(threading.Thread(
            target=vehiculo_estres, args=(i,      "NORTE")))
        hilos.append(threading.Thread(
            target=vehiculo_estres, args=(i + 50, "SUR"  )))

    for h in hilos: h.start()
    for h in hilos: h.join()

    puente.reporte()
    print(f"  Resultado: "
          f"{'INVARIANTE RESPETADO ' if puente.violaciones == 0 else 'FALLO '}")


# ── MAIN ─────────────────────────────────────────────────────────
def main():
    print("=" * 60)
    print("VERSIÓN 2 — ROBUSTA")
    print("Mecanismo: relevo por conteo de espera")
    print("=" * 60)

    prueba_normal()
    prueba_carga_adversa()
    prueba_estres()

    print()



if __name__ == "__main__":
    main()
