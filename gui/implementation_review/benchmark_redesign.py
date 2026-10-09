"""Compare 200-item fill and scroll in separate processes on the same machine."""
import argparse
import importlib
import json
from pathlib import Path
from statistics import median
import subprocess
import sys
from time import perf_counter

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", action="store_true")
    parser.add_argument("--mode", choices=["grid", "list"])
    parser.add_argument("--label")
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if args.baseline:
        for name, filename in [
            ("applauncher.gui.styles", "applauncher/gui/styles.py"),
            ("applauncher.gui.widgets.notes_widget", "applauncher/gui/widgets/notes_widget.py"),
            ("applauncher.gui.widgets", "applauncher/gui/widgets/__init__.py"),
            ("applauncher.gui.app", "applauncher/gui/app.py"),
        ]:
            module = importlib.import_module(name)
            source = subprocess.check_output(["git", "show", f"90bc36b:{filename}"], cwd=ROOT)
            exec(compile(source, filename, "exec"), module.__dict__)
    from PySide6.QtWidgets import QApplication
    from applauncher.gui.styles import apply_design_system
    from ui_fixture import isolated_window, settle

    app = QApplication([])
    app.setStyle("Fusion")
    apply_design_system(app)
    output = Path(__file__).resolve().parent
    label = "baseline" if args.baseline else "redesign"
    result = {"variant": label, "platform": app.platformName(), "count": 200,
              "repeats": 3, "scroll_steps": 40, "modes": {}}
    with isolated_window(output / ("benchmark_fixture_" + label), count=200) as window:
        window.resize(1000, 620)
        window.show()
        settle()
        items = list(window.service.repository.apps)
        for mode, container, fill in [
            ("grid", window.grid_widget, window.populate_grid),
            ("list", window.list_container, window.populate_list),
        ]:
            if args.mode and mode != args.mode:
                continue
            window.view_stack.setCurrentWidget(container)
            fill(items)
            settle()  # Warm caches before taking measurements.
            fill_times, scroll_times = [], []
            if args.profile:
                import cProfile
                profiler = cProfile.Profile()
                profiler.enable()
            for repeat in range(3):
                start = perf_counter()
                fill(items)
                settle()
                fill_times.append(perf_counter() - start)
                bar = window.scroll_area.verticalScrollBar()
                start = perf_counter()
                for index in range(40):
                    bar.setValue(round(bar.maximum() * (index % 20) / 19))
                    app.processEvents()
                settle()
                scroll_times.append(perf_counter() - start)
            if args.profile:
                profiler.disable()
                profiler.dump_stats(str(output / f"profile_{label}_{mode}.pstats"))
                import pstats
                pstats.Stats(profiler).sort_stats("cumulative").print_stats(25)
            result["modes"][mode] = {
                "fill_seconds": fill_times, "fill_median": median(fill_times),
                "scroll_seconds": scroll_times, "scroll_median": median(scroll_times),
                "scroll_max": bar.maximum(), "size": [window.width(), window.height()],
            }
    (output / f"benchmark_{args.label or label}.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
