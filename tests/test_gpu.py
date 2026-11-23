"""Pruebas de detección de gráficas con un sysfs simulado.

Ejecutar:  .venv/bin/python -m unittest discover -s tests -v
"""

import os
import tempfile
import unittest

from rgbeast import gpu

PCI_IDS = """\
# base mínima para las pruebas
1002  Advanced Micro Devices, Inc. [AMD/ATI]
\t15bf  Phoenix1 [Radeon 780M]
\t7480  Navi 33 [Radeon RX 7600/7600 XT/7600M XT/7600S/7700S / PRO W7600]
8086  Intel Corporation
\t7d67  Arrow Lake-S [Intel Graphics]
"""


def write(root, rel, value):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(str(value) + "\n")


def amd_card(root, n, device, vram, status="active", hw=True, power_file="power1_average"):
    base = f"sys/class/drm/card{n}/device"
    write(root, f"{base}/vendor", "0x1002")
    write(root, f"{base}/device", device)
    write(root, f"{base}/mem_info_vram_total", vram)
    write(root, f"{base}/gpu_busy_percent", 37)
    write(root, f"{base}/power/runtime_status", status)
    if hw:
        h = f"{base}/hwmon/hwmon{n + 3}"
        write(root, f"{h}/name", "amdgpu")
        write(root, f"{h}/temp1_label", "edge")
        write(root, f"{h}/temp1_input", 61000)
        write(root, f"{h}/temp2_label", "junction")
        write(root, f"{h}/temp2_input", 70000)
        write(root, f"{h}/{power_file}", 45_500_000)
        write(root, f"{h}/power1_cap", 100_000_000)
        write(root, f"{h}/freq1_input", 2_100_000_000)


class AmdTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "usr/share/hwdata/pci.ids", PCI_IDS)

    def tearDown(self):
        self.tmp.cleanup()

    def test_dedicada_lee_todo(self):
        amd_card(self.root, 0, "0x7480", 8 << 30)
        (g,) = gpu.detect(self.root)
        self.assertEqual(g.kind, "amd")
        self.assertTrue(g.discrete)
        self.assertEqual(g.name, "Radeon RX 7600")
        self.assertEqual(g.sample(), {"temp": 61.0, "util": 37, "power": 45.5,
                                      "power_limit": 100.0, "clock": 2100.0})

    def test_kernel_nuevo_usa_power1_input(self):
        amd_card(self.root, 0, "0x7480", 8 << 30, power_file="power1_input")
        (g,) = gpu.detect(self.root)
        self.assertEqual(g.sample()["power"], 45.5)

    def test_apu_es_integrada(self):
        amd_card(self.root, 0, "0x15bf", 512 << 20)
        (g,) = gpu.detect(self.root)
        self.assertFalse(g.discrete)
        self.assertEqual(g.name, "Radeon 780M")

    def test_dedicada_dormida_no_se_despierta(self):
        amd_card(self.root, 0, "0x7480", 8 << 30, status="suspended")
        (g,) = gpu.detect(self.root)
        self.assertEqual(g.sample(), {"asleep": True})

    def test_portatil_hibrido_prefiere_dedicada(self):
        amd_card(self.root, 0, "0x15bf", 512 << 20)   # APU primero en el bus
        amd_card(self.root, 1, "0x7480", 8 << 30)
        gs = gpu.detect(self.root)
        self.assertEqual([g.name for g in gs], ["Radeon RX 7600", "Radeon 780M"])

    def test_sin_hwmon_no_falla(self):
        amd_card(self.root, 0, "0x7480", 8 << 30, hw=False)
        (g,) = gpu.detect(self.root)
        self.assertEqual(g.sample(), {"util": 37})


class NombresTests(unittest.TestCase):
    def test_nombre_generico_lleva_nombre_en_clave(self):
        self.assertEqual(gpu._short("Arrow Lake-S [Intel Graphics]"), "Intel Graphics (Arrow Lake)")

    def test_nombre_comercial(self):
        self.assertEqual(gpu._short("Navi 33 [Radeon RX 7600M XT]"), "Radeon RX 7600M XT")


if __name__ == "__main__":
    unittest.main()


class FakeNvml:
    """Sustituto de libnvidia-ml: cuenta inits/shutdowns y lecturas."""

    def __init__(self):
        self.inits = self.shutdowns = self.reads = 0

    def nvmlInit_v2(self):
        self.inits += 1
        return 0

    def nvmlShutdown(self):
        self.shutdowns += 1
        return 0

    def nvmlDeviceGetHandleByIndex_v2(self, i, ref):
        return 0

    def nvmlDeviceGetName(self, h, buf, n):
        buf.value = b"NVIDIA GeForce RTX 5070 Laptop GPU"
        return 0

    def nvmlDeviceGetTemperature(self, h, s, ref):
        self.reads += 1
        ref._obj.value = 55
        return 0

    def __getattr__(self, name):  # resto de consultas: sin dato
        return lambda *a: 1


class NvidiaTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        write(self.root, "usr/share/hwdata/pci.ids",
              PCI_IDS + "10de  NVIDIA Corporation\n\t2d58  GB206M [GeForce RTX 5070 Max-Q / Mobile]\n")
        base = "sys/class/drm/card0/device"
        write(self.root, f"{base}/vendor", "0x10de")
        write(self.root, f"{base}/device", "0x2d58")
        self.status = os.path.join(self.root, base, "power/runtime_status")
        write(self.root, f"{base}/power/runtime_status", "active")
        os.makedirs(os.path.join(self.root, "proc"))
        self.fake = FakeNvml()
        self._cdll = gpu.ctypes.CDLL
        gpu.ctypes.CDLL = lambda name: self.fake

    def tearDown(self):
        gpu.ctypes.CDLL = self._cdll
        self.tmp.cleanup()

    def user(self, pid, target):
        fd = os.path.join(self.root, "proc", str(pid), "fd")
        os.makedirs(fd, exist_ok=True)
        os.symlink(target, os.path.join(fd, str(len(os.listdir(fd)))))

    def gpu(self):
        (g,) = gpu.detect(self.root)
        g.USERS_EVERY = 0
        return g

    def test_nombre_y_no_retiene_nvml(self):
        g = self.gpu()
        self.assertEqual(g.name, "RTX 5070 Laptop GPU")
        self.assertEqual(self.fake.inits, self.fake.shutdowns)

    def test_dormida_usa_nombre_pci_sin_tocarla(self):
        write(self.root, "sys/class/drm/card0/device/power/runtime_status", "suspended")
        g = self.gpu()
        self.assertEqual(g.name, "RTX 5070 Max-Q")
        self.assertEqual(self.fake.inits, 0)
        self.assertEqual(g.sample(), {"asleep": True})

    def test_sin_otros_usuarios_no_consulta(self):
        self.user(9001, "/dev/nvidiactl")      # no es la gráfica en sí
        self.user(9002, "/dev/nvidia-uvm")
        g = self.gpu()
        self.assertEqual(g.sample(), {"asleep": True})
        self.assertEqual(self.fake.reads, 0)
        self.assertEqual(self.fake.inits, self.fake.shutdowns)

    def test_con_juego_consulta_y_al_cerrar_suelta(self):
        g = self.gpu()
        self.user(9003, "/dev/nvidia0")
        self.assertEqual(g.sample(), {"temp": 55})
        self.assertGreater(self.fake.inits, self.fake.shutdowns)   # abierta
        import shutil
        shutil.rmtree(os.path.join(self.root, "proc", "9003"))
        self.assertEqual(g.sample(), {"asleep": True})
        self.assertEqual(self.fake.inits, self.fake.shutdowns)     # soltada
