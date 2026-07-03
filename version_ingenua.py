"""
=========================================================
VERSIÓN 0 - IMPLEMENTACIÓN INGENUA (SIN SINCRONIZACIÓN)

Autores:
Jefferson Gomez 
Juan Camilo Morales 
Marilyn Grijalba
Juan Diego Quiñonez
Jorge Castro
=========================================================

Objetivo:
Demostrar de forma determinista una condición de carrera
que viola el invariante del puente.

Invariante:
"Nunca pueden existir vehículos de ambos sentidos
simultáneamente sobre el puente."

La Barrier NO hace parte de la solución.
Únicamente se utiliza para que todos los vehículos
intenten entrar al mismo tiempo y el fallo ocurra
en todas las ejecuciones.
"""

import threading
import time


class Puente:

    def __init__(self):

        # Vehículos actualmente sobre el puente
        self.norte = 0
        self.sur = 0

        # Solo para llevar un registro del estado
        self.evento = 0

        # Barrier para reproducir SIEMPRE el fallo
        self.barrier = threading.Barrier(20)

        # Solo evita que las impresiones se mezclen
        self.print_lock = threading.Lock()

    def imprimir_estado(self, vehiculo, accion):

        with self.print_lock:

            self.evento += 1

            print("\n" + "=" * 60)
            print(f"EVENTO #{self.evento}")
            print("=" * 60)

            print(f"Vehículo : {vehiculo.nombre}")
            print(f"Dirección: {vehiculo.direccion}")
            print(f"Acción   : {accion}")

            print("\nEstado actual del puente:")

            print(f"   Norte : {self.norte}")
            print(f"   Sur   : {self.sur}")

            if self.norte > 0 and self.sur > 0:
                print("\n❌ INVARIANTE VIOLADO")
            else:
                print("\n✅ Invariante satisfecho")

            print("=" * 60)

    def verificar_invariante(self):

        assert not (self.norte > 0 and self.sur > 0), f"""

============================================================
                COLISIÓN DETECTADA
============================================================

El invariante del puente fue violado.

Vehículos en el puente:

    Norte : {self.norte}
    Sur   : {self.sur}

No pueden existir vehículos de ambos sentidos
cruzando simultáneamente.

============================================================

"""

    def entrar(self, vehiculo):

        # Todos llegan exactamente al mismo tiempo
        self.barrier.wait()

        print(f"{vehiculo.nombre} observa el puente libre.")

        # Hace muchísimo más probable la condición de carrera
        time.sleep(0.2)

        if vehiculo.direccion == "NORTE":
            self.norte += 1
        else:
            self.sur += 1

        self.imprimir_estado(vehiculo, "ENTRA AL PUENTE")

        # Aquí verificamos el invariante
        self.verificar_invariante()

    def salir(self, vehiculo):

        time.sleep(1)

        if vehiculo.direccion == "NORTE":
            self.norte -= 1
        else:
            self.sur -= 1

        self.imprimir_estado(vehiculo, "SALE DEL PUENTE")


class Vehiculo(threading.Thread):

    def __init__(self, nombre, direccion, puente):

        super().__init__()

        self.nombre = nombre
        self.direccion = direccion
        self.puente = puente

    def run(self):

        print(f"{self.nombre} llega desde el {self.direccion}")

        self.puente.entrar(self)

        print(f"{self.nombre} está cruzando...")

        self.puente.salir(self)


def main():

    puente = Puente()

    hilos = []

    # 10 vehículos por cada sentido
    for i in range(10):

        hilos.append(
            Vehiculo(
                f"N-{i+1}",
                "NORTE",
                puente
            )
        )

        hilos.append(
            Vehiculo(
                f"S-{i+1}",
                "SUR",
                puente
            )
        )

    for h in hilos:
        h.start()

    for h in hilos:
        h.join()


if __name__ == "__main__":
    main()