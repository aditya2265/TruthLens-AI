"""Benchmark script to measure before/after performance numbers accurately."""
import subprocess
import sys
import time
import re
import requests

PYTHON_EXE = r".\.venv\Scripts\python.exe"
BASE_URL = "http://127.0.0.1:5000"
ENGLISH_PARAGRAPH = (
    "The Senate Budget Committee held a bipartisan hearing on federal discretionary spending targets "
    "for the upcoming fiscal year. Lawmakers from both parties discussed allocating infrastructure grants "
    "to bridge repair initiatives and public water system upgrades across thirty states. Agency officials "
    "emphasized that formal budget appropriations will require further legislative compromise before the deadline."
)


def measure_import_time(runs=3):
    times = []
    for i in range(runs):
        cmd = [PYTHON_EXE, "-c", "import time; t0 = time.perf_counter(); import src.app; print(f'{(time.perf_counter() - t0):.4f}')"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        t = float(res.stdout.strip().splitlines()[-1])
        times.append(t)
    return times


def measure_model_load_time(runs=3):
    times = []
    for i in range(runs):
        cmd = [PYTHON_EXE, "-c", "import time; from src.predict import load_model; t0 = time.perf_counter(); load_model(force_reload=True); print(f'{(time.perf_counter() - t0):.4f}')"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        t = float(res.stdout.strip().splitlines()[-1])
        times.append(t)
    return times


def run_benchmarks():
    print("--- 1. Python Import Time (3 runs) ---")
    import_times = measure_import_time(3)
    for i, t in enumerate(import_times, 1):
        print(f"Run {i}: {t:.4f}s ({t*1000:.1f}ms)")
    print(f"Average Import Time: {sum(import_times)/len(import_times):.4f}s")

    print("\n--- 2. Model Load Time (3 runs) ---")
    model_times = measure_model_load_time(3)
    for i, t in enumerate(model_times, 1):
        print(f"Run {i}: {t:.4f}s ({t*1000:.1f}ms)")
    print(f"Average Model Load Time: {sum(model_times)/len(model_times):.4f}s")

    print("\n--- Starting local server (.venv/Scripts/python.exe -m src.app) ---")
    proc = subprocess.Popen([PYTHON_EXE, "-m", "src.app"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    # Wait for server to become responsive
    session = requests.Session()
    started = False
    for attempt in range(40):
        try:
            r = session.get(f"{BASE_URL}/health", timeout=1.0)
            if r.status_code in (200, 503):
                started = True
                print("Server is up and responding!")
                break
        except Exception:
            time.sleep(0.5)

    if not started:
        proc.kill()
        out, err = proc.communicate()
        print("Server failed to start:\n", out, err)
        sys.exit(1)

    try:
        # Measure GET /
        print("\n--- 3. GET / (3 runs) ---")
        get_root_times = []
        for i in range(3):
            t0 = time.perf_counter()
            resp = session.get(f"{BASE_URL}/", timeout=60.0)
            t = time.perf_counter() - t0
            get_root_times.append(t)
            print(f"Run {i+1}: status={resp.status_code}, time={t:.4f}s ({t*1000:.1f}ms)")
        print(f"Average GET /: {sum(get_root_times)/len(get_root_times):.4f}s")

        # Measure GET /health
        print("\n--- 4. GET /health (3 runs) ---")
        get_health_times = []
        for i in range(3):
            t0 = time.perf_counter()
            resp = session.get(f"{BASE_URL}/health", timeout=10.0)
            t = time.perf_counter() - t0
            get_health_times.append(t)
            print(f"Run {i+1}: status={resp.status_code}, time={t:.4f}s ({t*1000:.1f}ms)")
        print(f"Average GET /health: {sum(get_health_times)/len(get_health_times):.4f}s")

        # Measure POST /predict (English paragraph)
        print("\n--- 5. POST /predict (English paragraph) (3 runs) ---")
        post_predict_times = []
        for i in range(3):
            # Fetch CSRF token
            r_page = session.get(f"{BASE_URL}/")
            csrf_token_match = re.search(r'name="csrf_token"\s+value="([^"]+)"', r_page.text)
            csrf_token = csrf_token_match.group(1) if csrf_token_match else ""

            t0 = time.perf_counter()
            resp = session.post(
                f"{BASE_URL}/predict",
                data={
                    "csrf_token": csrf_token,
                    "input_mode": "text",
                    "news_text": ENGLISH_PARAGRAPH,
                },
                timeout=60.0,
            )
            t = time.perf_counter() - t0
            post_predict_times.append(t)
            print(f"Run {i+1}: status={resp.status_code}, time={t:.4f}s ({t*1000:.1f}ms)")
        print(f"Average POST /predict: {sum(post_predict_times)/len(post_predict_times):.4f}s")

        # Measure /api/news-feed
        print("\n--- 6. GET /api/news-feed (3 runs) ---")
        feed_times = []
        for i in range(3):
            t0 = time.perf_counter()
            resp = session.get(f"{BASE_URL}/api/news-feed", timeout=60.0)
            t = time.perf_counter() - t0
            feed_times.append(t)
            print(f"Run {i+1}: status={resp.status_code}, time={t:.4f}s ({t*1000:.1f}ms)")
        print(f"Average /api/news-feed: {sum(feed_times)/len(feed_times):.4f}s")

        # Output Summary Table
        print("\n" + "=" * 60)
        print("SUMMARY TABLE (BEFORE)")
        print("=" * 60)
        print(f"{'Operation':<35} | {'Run 1':<8} | {'Run 2':<8} | {'Run 3':<8} | {'Average':<8}")
        print("-" * 60)
        rows = [
            ("Python import time (src.app)", import_times),
            ("Model load time", model_times),
            ("GET /", get_root_times),
            ("GET /health", get_health_times),
            ("POST /predict (English)", post_predict_times),
            ("GET /api/news-feed", feed_times),
        ]
        for name, r_list in rows:
            print(f"{name:<35} | {r_list[0]*1000:6.1f}ms | {r_list[1]*1000:6.1f}ms | {r_list[2]*1000:6.1f}ms | {sum(r_list)/len(r_list)*1000:6.1f}ms")
        print("=" * 60)

    finally:
        print("\nTerminating local server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        print("Local server stopped.")


if __name__ == "__main__":
    run_benchmarks()
