import os
import signal
import sys

from gr.airband_demodulator import airband_demodulator


def main():
    if not os.path.exists("./tmp"):
        os.makedirs("./tmp")

    demodulator = airband_demodulator()

    def sig_handler(sig, frame):
        demodulator.stop()
        demodulator.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    demodulator.start()
    demodulator.flowgraph_started.set()
    demodulator.wait()


if __name__ == "__main__":
    main()
