import threading
import time
import random

class PuenteSeguro:

    def __init__(self):
        self._condition      = threading.Condition()  # Lock + wait/notify
        self._direction      = None  # Sentido actual del puente (None = libre)
        self._en_puente      = 0     # Total de vehículos en el puente
        self._norte_en_puente = 0    # Para verificar el invariante
        self._sur_en_puente   = 0    # Para verificar el invariante

        # Métricas
        self.total_cruzados  = {"NORTE": 0, "SUR": 0}
        self.max_simultaneos = 0

    # ── INVARIANTE EJECUTABLE ────────────────────────────────────
    def _verificar_invariante(self):
        assert not (self._norte_en_puente > 0 and self._sur_en_puente > 0), (
            f" INVARIANTE VIOLADO "
            f"Norte={self._norte_en_puente}, Sur={self._sur_en_puente}"
        )

    # ── ENTRADA AL PUENTE ────────────────────────────────────────
    def entrar(self, vid, direction):
        with self._condition:
            # Espera activa eficiente (wait libera el lock mientras duerme)
            while self._direction is not None and self._direction != direction:
                self._condition.wait()

            # Tomamos posesión del sentido si somos el primero
            self._direction = direction
            self._en_puente += 1
            if direction == "NORTE":
                self._norte_en_puente += 1
            else:
                self._sur_en_puente += 1

            self._verificar_invariante()

            if self._en_puente > self.max_simultaneos:
                self.max_simultaneos = self._en_puente

    # ── SALIDA DEL PUENTE ────────────────────────────────────────
    def salir(self, vid, direction):
        with self._condition:
            self._en_puente -= 1
            if direction == "NORTE":
                self._norte_en_puente -= 1
            else:
                self._sur_en_puente -= 1
            self.total_cruzados[direction] += 1

            # Si somos el último: liberamos el puente
            if self._en_puente == 0:
                self._direction = None
                self._condition.notify_all()  # Despierta hilos del otro sentido


def vehiculo(vid, direction, puente, tiempo_cruce=0.05):
    """Hilo que representa un vehículo."""
    puente.entrar(vid, direction)
    time.sleep(tiempo_cruce)          # Simula el tiempo de cruce
    puente.salir(vid, direction)


# ── DEMOSTRACIÓN DE INANICIÓN ────────────────────────────────────
def demo_inaniacion():
    print()
    print("── Demo inanición potencial ──────────────────────────")
    puente = PuenteSeguro()
    tiempos_sur = []
    inicio_global = time.time()

    def vehiculo_norte_continuo():
        """Genera vehículos del norte sin parar durante 2 segundos."""
        deadline = time.time() + 2.0
        vid = 0
        while time.time() < deadline:
            puente.entrar(vid, "NORTE")
            time.sleep(0.02)
            puente.salir(vid, "NORTE")
            vid += 1

    def vehiculo_sur_mide(vid):
        t0 = time.time()
        puente.entrar(vid, "SUR")
        tiempo_espera = time.time() - t0
        tiempos_sur.append(tiempo_espera)
        time.sleep(0.02)
        puente.salir(vid, "SUR")

    gen_norte = threading.Thread(target=vehiculo_norte_continuo)
    gen_norte.start()

    time.sleep(0.1)  # Deja que el norte tome el puente
    hilos_sur = []
    for i in range(5):
        h = threading.Thread(target=vehiculo_sur_mide, args=(i,))
        hilos_sur.append(h)
        h.start()
        time.sleep(0.05)

    gen_norte.join()
    for h in hilos_sur:
        h.join()

    print(f"  Tiempo de espera vehículos SUR: "
          f"{[f'{t:.3f}s' for t in tiempos_sur]}")
    print("")


def main():

    puente = PuenteSeguro()
    hilos  = []

    # 15 norte + 15 sur con llegadas escalonadas
    for i in range(15):
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i,      "NORTE", puente, random.uniform(0.02, 0.06))))
        hilos.append(threading.Thread(
            target=vehiculo,
            args=(i + 15, "SUR",   puente, random.uniform(0.02, 0.06))))

    random.shuffle(hilos)  # Orden de llegada aleatorio

    for h in hilos:
        h.start()
        time.sleep(random.uniform(0, 0.01))  # Llegadas no simultáneas
    for h in hilos:
        h.join()

    print(f"  Cruzados Norte: {puente.total_cruzados['NORTE']}")
    print(f"  Cruzados Sur  : {puente.total_cruzados['SUR']}")
    print(f"  Máximo simultáneo en puente: {puente.max_simultaneos}")
    print(f"  Invariante: NUNCA violado ")
    print()

    demo_inaniacion()


if __name__ == "__main__":
    main()
