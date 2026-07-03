import threading
import time
import statistics
import sys

# ── Importar la clase del puente robusto ────────────────────────
# Copiamos la clase aquí para que el harness sea autónomo

class PuenteEquitativo:
    def __init__(self):
        self._condition        = threading.Condition()
        self._direction        = None
        self._en_puente        = 0
        self._esperando        = {"NORTE": 0, "SUR": 0}
        self._norte_en_puente  = 0
        self._sur_en_puente    = 0
        self.total_cruzados    = {"NORTE": 0, "SUR": 0}
        self.tiempos_espera    = {"NORTE": [], "SUR": []}
        self.max_simultaneos   = 0
        self.violaciones       = 0

    def _verificar_invariante(self):
        """Aserción ejecutable — aborta si el invariante se viola."""
        ok = not (self._norte_en_puente > 0 and self._sur_en_puente > 0)
        if not ok:
            self.violaciones += 1
        assert ok, (
            f"INVARIANTE VIOLADO: "
            f"Norte={self._norte_en_puente}, Sur={self._sur_en_puente}"
        )

    def _puede_entrar(self, direction):
        contrario = "SUR" if direction == "NORTE" else "NORTE"
        if self._direction is None:
            return True
        if self._direction != direction:
            return False
        if self._esperando[contrario] > 0:
            return False
        return True

    def entrar(self, vid, direction):
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
        with self._condition:
            self.tiempos_espera[direction].append(time.time() - t_llegada)

    def salir(self, vid, direction):
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


# ── Utilidades del harness ───────────────────────────────────────

PASS = "PASS ✓"
FAIL = "FAIL ✗"

def vehiculo(vid, direction, puente, tiempo_cruce=0.03):
    puente.entrar(vid, direction)
    time.sleep(tiempo_cruce)
    puente.salir(vid, direction)

def correr_con_timeout(hilos, timeout_seg):
    """
    Corre una lista de hilos y falla si no terminan en timeout_seg.
    Detecta deadlocks: si el sistema se congela, el timeout dispara.
    """
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(timeout=timeout_seg)
        if h.is_alive():
            return False   # Deadlock detectado
    return True

def separador(titulo):
    print(f"\n{'─'*55}")
    print(f"  {titulo}")
    print(f"{'─'*55}")


# ── PRUEBA 1: Invariante bajo carga normal ───────────────────────

def prueba_carga_normal():
    separador("PRUEBA 1 — Invariante bajo carga normal (20N + 20S)")
    puente = PuenteEquitativo()
    hilos  = []

    import random
    for i in range(20):
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i,      "NORTE", puente, random.uniform(0.01, 0.05))))
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i + 20, "SUR",   puente, random.uniform(0.01, 0.05))))

    random.shuffle(hilos)
    ok = correr_con_timeout(hilos, timeout_seg=30)

    assert ok,                        "Timeout — posible deadlock"
    assert puente.violaciones == 0,   "Invariante violado"
    assert puente.total_cruzados["NORTE"] == 20, "No cruzaron todos del norte"
    assert puente.total_cruzados["SUR"]   == 20, "No cruzaron todos del sur"

    print(f"  Cruzados Norte : {puente.total_cruzados['NORTE']}")
    print(f"  Cruzados Sur   : {puente.total_cruzados['SUR']}")
    print(f"  Max simultáneos: {puente.max_simultaneos}")
    print(f"  Violaciones    : {puente.violaciones}")
    print(f"  Resultado      : {PASS}")


# ── PRUEBA 2: Invariante bajo estrés (50N + 50S simultáneos) ────

def prueba_estres():
    separador("PRUEBA 2 — Estrés: 50N + 50S lanzados simultáneamente")
    puente  = PuenteEquitativo()
    barrier = threading.Barrier(100)

    import random
    def vehiculo_estres(vid, direction):
        barrier.wait()
        vehiculo(vid, direction, puente, random.uniform(0.005, 0.03))

    hilos = []
    for i in range(50):
        hilos.append(threading.Thread(
            target=vehiculo_estres, args=(i,      "NORTE")))
        hilos.append(threading.Thread(
            target=vehiculo_estres, args=(i + 50, "SUR"  )))

    ok = correr_con_timeout(hilos, timeout_seg=60)

    assert ok,                         "Timeout — posible deadlock"
    assert puente.violaciones == 0,    "Invariante violado bajo estrés"
    assert puente.total_cruzados["NORTE"] == 50, "No cruzaron todos del norte"
    assert puente.total_cruzados["SUR"]   == 50, "No cruzaron todos del sur"

    print(f"  Cruzados Norte : {puente.total_cruzados['NORTE']}")
    print(f"  Cruzados Sur   : {puente.total_cruzados['SUR']}")
    print(f"  Max simultáneos: {puente.max_simultaneos}")
    print(f"  Violaciones    : {puente.violaciones}")
    print(f"  Resultado      : {PASS}")


# ── PRUEBA 3: Equidad con carga adversa ─────────────────────────

def prueba_equidad():
    separador("PRUEBA 3 — Equidad: Norte continuo vs Sur esporádico")
    puente       = PuenteEquitativo()
    esperas_sur  = []
    activo       = True
    LIMITE_ESPERA_MS = 500   # Ningún vehículo sur debe esperar más de esto

    def generador_norte():
        vid = 0
        while activo:
            t = threading.Thread(
                target=vehiculo, args=(vid, "NORTE", puente, 0.02))
            t.start()
            time.sleep(0.01)
            vid += 1

    def vehiculo_sur_mide(vid):
        t0 = time.time()
        puente.entrar(vid, "SUR")
        esperas_sur.append((vid, (time.time() - t0) * 1000))
        time.sleep(0.02)
        puente.salir(vid, "SUR")

    gen = threading.Thread(target=generador_norte)
    gen.start()
    time.sleep(0.1)

    hilos_sur = []
    for i in range(10):
        h = threading.Thread(target=vehiculo_sur_mide, args=(i,))
        hilos_sur.append(h)
        h.start()
        time.sleep(0.08)

    for h in hilos_sur:
        h.join(timeout=10)
        assert not h.is_alive(), f"Vehículo sur {i} nunca cruzó — inanición"

    activo = False
    gen.join(timeout=3)

    assert len(esperas_sur) == 10, "No cruzaron todos los del sur"

    max_espera = max(e for _, e in esperas_sur)
    assert max_espera < LIMITE_ESPERA_MS, (
        f"Espera máxima {max_espera:.0f}ms supera límite {LIMITE_ESPERA_MS}ms"
    )

    print(f"  {'VID':>4}  {'Espera':>10}")
    for vid, espera in esperas_sur:
        print(f"  {vid:>4}  {espera:>9.1f}ms")
    print(f"  Espera máxima : {max_espera:.1f}ms  (límite: {LIMITE_ESPERA_MS}ms)")
    print(f"  Resultado     : {PASS}")


# ── PRUEBA 4: Sin deadlock ───────────────────────────────────────

def prueba_sin_deadlock():
    separador("PRUEBA 4 — Sin deadlock (timeout 10s)")
    TIMEOUT = 10
    puente  = PuenteEquitativo()

    import random
    hilos = []
    for i in range(30):
        d = "NORTE" if i % 2 == 0 else "SUR"
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i, d, puente, random.uniform(0.01, 0.04))))

    ok = correr_con_timeout(hilos, timeout_seg=TIMEOUT)

    assert ok, f"El sistema no terminó en {TIMEOUT}s — DEADLOCK detectado"

    print(f"  Todos los hilos terminaron antes de {TIMEOUT}s")
    print(f"  Violaciones : {puente.violaciones}")
    print(f"  Resultado   : {PASS}")


# ── PRUEBA 5: Caso límite — un solo vehículo ────────────────────

def prueba_un_vehiculo():
    separador("PRUEBA 5 — Caso límite: un solo vehículo")
    puente = PuenteEquitativo()
    h = threading.Thread(target=vehiculo, args=(0, "NORTE", puente, 0.05))
    ok = correr_con_timeout([h], timeout_seg=5)

    assert ok,                       "El vehículo nunca terminó"
    assert puente.violaciones == 0,  "Invariante violado con un solo vehículo"
    assert puente.total_cruzados["NORTE"] == 1, "El vehículo no cruzó"

    print(f"  Cruzados: {puente.total_cruzados['NORTE']}")
    print(f"  Resultado: {PASS}")


# ── PRUEBA 6: Todos del mismo sentido ───────────────────────────

def prueba_mismo_sentido():
    separador("PRUEBA 6 — Caso límite: 20 vehículos todos del NORTE")
    puente  = PuenteEquitativo()
    barrier = threading.Barrier(20)

    def vehiculo_norte(vid):
        barrier.wait()
        vehiculo(vid, "NORTE", puente, 0.02)

    hilos = [threading.Thread(target=vehiculo_norte, args=(i,))
             for i in range(20)]
    ok = correr_con_timeout(hilos, timeout_seg=15)

    assert ok,                        "Timeout — posible deadlock"
    assert puente.violaciones == 0,   "Invariante violado"
    assert puente.total_cruzados["NORTE"] == 20, "No cruzaron todos"
    assert puente.total_cruzados["SUR"]   == 0,  "No debería haber del sur"

    print(f"  Cruzados Norte : {puente.total_cruzados['NORTE']}")
    print(f"  Cruzados Sur   : {puente.total_cruzados['SUR']}")
    print(f"  Max simultáneos: {puente.max_simultaneos}")
    print(f"  Resultado      : {PASS}")


# ── PRUEBA 7: Throughput ─────────────────────────────────────────

def prueba_throughput():
    separador("PRUEBA 7 — Medición de throughput")
    puente   = PuenteEquitativo()
    DURACION = 3.0   # segundos de medición
    conteo   = {"valor": 0}
    lock_c   = threading.Lock()
    activo   = True

    def vehiculo_throughput(vid, direction):
        while activo:
            puente.entrar(vid, direction)
            time.sleep(0.02)
            puente.salir(vid, direction)
            with lock_c:
                conteo["valor"] += 1

    hilos = []
    for i in range(5):
        hilos.append(threading.Thread(
            target=vehiculo_throughput, args=(i,     "NORTE"), daemon=True))
        hilos.append(threading.Thread(
            target=vehiculo_throughput, args=(i + 5, "SUR"  ), daemon=True))

    t_inicio = time.time()
    for h in hilos:
        h.start()

    time.sleep(DURACION)
    activo = False

    t_total    = time.time() - t_inicio
    throughput = conteo["valor"] / t_total

    print(f"  Duración      : {t_total:.2f}s")
    print(f"  Total cruzados: {conteo['valor']}")
    print(f"  Throughput    : {throughput:.1f} vehículos/segundo")

    # Métricas de espera acumuladas
    for d in ("NORTE", "SUR"):
        t = puente.tiempos_espera[d]
        if t:
            print(f"  Espera {d:<5} : "
                  f"prom={statistics.mean(t)*1000:.1f}ms  "
                  f"max={max(t)*1000:.1f}ms")
    print(f"  Resultado     : {PASS}")


# ── RUNNER PRINCIPAL ─────────────────────────────────────────────

def main():
    print("=" * 55)
    print("  HARNESS DE VERIFICACIÓN — Puente un solo carril")
    print("  Sistemas Operativos — Universidad del Valle 2026-1")
    print("=" * 55)

    pruebas = [
        ("Carga normal",       prueba_carga_normal),
        ("Estrés 50+50",       prueba_estres),
        ("Equidad adversa",    prueba_equidad),
        ("Sin deadlock",       prueba_sin_deadlock),
        ("Un vehículo",        prueba_un_vehiculo),
        ("Mismo sentido",      prueba_mismo_sentido),
        ("Throughput",         prueba_throughput),
    ]

    resultados = []
    for nombre, prueba in pruebas:
        try:
            prueba()
            resultados.append((nombre, True, None))
        except AssertionError as e:
            print(f"  Resultado : {FAIL}")
            print(f"  Error     : {e}")
            resultados.append((nombre, False, str(e)))
        except Exception as e:
            print(f"  Resultado : {FAIL} (excepción inesperada)")
            print(f"  Error     : {e}")
            resultados.append((nombre, False, str(e)))

    # Resumen final
    print(f"\n{'='*55}")
    print("  RESUMEN")
    print(f"{'='*55}")
    pasaron = sum(1 for _, ok, _ in resultados if ok)
    for nombre, ok, error in resultados:
        estado = PASS if ok else FAIL
        print(f"  {estado}  {nombre}")
        if error:
            print(f"         → {error}")

    print(f"\n  Total: {pasaron}/{len(pruebas)} pruebas pasaron")
    print("=" * 55)

    if pasaron < len(pruebas):
        sys.exit(1)


if __name__ == "__main__":
    main()
