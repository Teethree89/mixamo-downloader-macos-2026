# Stdlib modules
import copy
import json
import os
import requests
import time

# Third-party modules
from PySide6 import QtCore


HEADERS = {
    "Accept": "application/json",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Content-Type": "application/json",
    "X-Api-Key": "mixamo2",
    "X-Requested-With": "XMLHttpRequest",
}

# All requests will be done through a session to improve performance.
session = requests.Session()


class MixamoDownloader(QtCore.QObject):
    """Bulk download animations from Mixamo."""

    finished = QtCore.Signal()
    total_tasks = QtCore.Signal(int)
    current_task = QtCore.Signal(int)
    log = QtCore.Signal(str)

    def __init__(self, path, mode, query=None, prefer_in_place=True):
        super().__init__()
        self.path = path
        self.mode = mode
        self.query = query
        self.prefer_in_place = prefer_in_place
        self.task = 1
        self.stop = False
        self.product_name = "animation"

    def _request_json(self, method, url, **kwargs):
        response = session.request(method, url, headers=HEADERS, timeout=60, **kwargs)
        response.raise_for_status()
        return response.json()

    def run(self):
        try:
            character = self._request_json(
                "GET", "https://www.mixamo.com/api/v1/characters/primary"
            )
            character_id = character.get("primary_character_id")
            character_name = character.get("primary_character_name")

            if not character_id:
                self.log.emit("Mixamo did not return a primary character. Select a character first.")
                return

            if self.mode == "tpose":
                self.total_tasks.emit(1)
                payload = self.build_tpose_payload(character_id, character_name)
                url = self.export_animation(character_id, payload)
                self.download_animation(url)
                return

            if self.mode == "all":
                anim_data = self.get_all_animations_data()
            elif self.mode == "query":
                anim_data = self.get_queried_animations_data(self.query)
            else:
                raise RuntimeError(f"Unknown download mode: {self.mode}")

            for anim_id, anim_name in anim_data.items():
                if self.stop:
                    self.log.emit("Download stopped by user.")
                    return

                self.log.emit(f"Preparing {anim_name}…")
                payload = self.build_animation_payload(character_id, anim_id)
                url = self.export_animation(character_id, payload)
                self.download_animation(url)

        except Exception as exc:
            self.log.emit(f"ERROR: {exc}")
        finally:
            self.finished.emit()

    def build_tpose_payload(self, character_id, character_name):
        self.product_name = character_name
        payload = {
            "character_id": character_id,
            "product_name": self.product_name,
            "type": "Character",
            "preferences": {"format": "fbx7_2019", "mesh": "t-pose"},
            "gms_hash": None,
        }
        return json.dumps(payload)

    def get_queried_animations_data(self, query):
        page_num = 1
        animations = []

        while True:
            params = {
                "limit": 96,
                "page": page_num,
                "type": "Motion",
                "query": query,
            }
            data = self._request_json(
                "GET", "https://www.mixamo.com/api/v1/products", params=params
            )
            animations.extend(data.get("results", []))
            num_pages = data.get("pagination", {}).get("num_pages", 1)
            if page_num >= num_pages:
                break
            page_num += 1

        anim_data = {
            animation["id"]: animation.get("description") or animation.get("name") or animation["id"]
            for animation in animations
        }
        self.total_tasks.emit(len(anim_data))
        return anim_data

    def get_all_animations_data(self):
        json_path = os.path.join(os.path.dirname(__file__), "mixamo_anims.json")
        with open(json_path, "r", encoding="utf-8") as file:
            anim_data = json.load(file)
        self.total_tasks.emit(len(anim_data))
        return anim_data

    @staticmethod
    def _param_label(param):
        """Best-effort extraction of a readable Mixamo animation parameter label."""
        if isinstance(param, dict):
            for key in ("name", "label", "display_name", "description", "key"):
                value = param.get(key)
                if isinstance(value, str) and value:
                    return value
            return ""
        if isinstance(param, (list, tuple)):
            for item in param[:-1]:
                if isinstance(item, str) and item:
                    return item
        return ""

    @staticmethod
    def _param_value(param):
        if isinstance(param, dict):
            for key in ("value", "default", "current"):
                if key in param:
                    try:
                        return int(param[key])
                    except (TypeError, ValueError):
                        pass
            return 0
        if isinstance(param, (list, tuple)) and param:
            try:
                return int(param[-1])
            except (TypeError, ValueError):
                return 0
        return 0

    def _prefer_native_in_place(self, gms_hash):
        """Set Mixamo's native In Place parameter when the animation exposes one.

        Mixamo stores animation-specific controls in gms_hash['params']. The exact
        shape is not formally documented, so this intentionally only changes a
        parameter when its metadata clearly identifies it as an in-place control.
        """
        params = gms_hash.get("params")
        if not isinstance(params, list):
            return False

        values = [self._param_value(param) for param in params]
        found = False

        for index, param in enumerate(params):
            label = self._param_label(param).strip().lower().replace("_", " ")
            normalized = " ".join(label.split())
            if "in place" in normalized or normalized in {"inplace", "in-place"}:
                values[index] = 1
                found = True
                break

        if found:
            gms_hash["params"] = ",".join(str(value) for value in values)
        return found

    def build_animation_payload(self, character_id, anim_id):
        data = self._request_json(
            "GET",
            f"https://www.mixamo.com/api/v1/products/{anim_id}",
            params={"similar": 0, "character_id": character_id},
        )

        self.product_name = data.get("description") or data.get("name") or anim_id
        animation_type = data["type"]

        preferences = {
            "format": "fbx7_2019",
            "skin": False,
            "fps": "24",
            "reducekf": "0",
        }

        gms_hash = copy.deepcopy(data["details"]["gms_hash"])
        original_params = copy.deepcopy(gms_hash.get("params"))

        in_place_applied = False
        if self.prefer_in_place:
            in_place_applied = self._prefer_native_in_place(gms_hash)

        if not in_place_applied:
            params = original_params
            if isinstance(params, list):
                values = [self._param_value(param) for param in params]
                gms_hash["params"] = ",".join(str(value) for value in values)
            elif isinstance(params, str):
                gms_hash["params"] = params

        gms_hash["overdrive"] = 0

        trim = gms_hash.get("trim")
        if isinstance(trim, (list, tuple)) and len(trim) >= 2:
            gms_hash["trim"] = [int(trim[0]), int(trim[1])]

        if self.prefer_in_place:
            if in_place_applied:
                self.log.emit(f"{self.product_name}: native Mixamo In Place enabled.")
            else:
                self.log.emit(f"{self.product_name}: no native In Place parameter exposed; using authored motion.")

        payload = {
            "character_id": character_id,
            "product_name": self.product_name,
            "type": animation_type,
            "preferences": preferences,
            "gms_hash": [gms_hash],
        }
        return json.dumps(payload)

    def export_animation(self, character_id, payload):
        response = session.post(
            "https://www.mixamo.com/api/v1/animations/export",
            data=payload,
            headers=HEADERS,
            timeout=60,
        )
        response.raise_for_status()

        status = None
        started = time.time()
        while status != "completed":
            if self.stop:
                return None
            if time.time() - started > 300:
                raise TimeoutError(f"Timed out waiting for Mixamo export of {self.product_name}")

            time.sleep(1)
            monitor = self._request_json(
                "GET",
                f"https://www.mixamo.com/api/v1/characters/{character_id}/monitor",
            )
            status = monitor.get("status")
            if status in {"failed", "error"}:
                raise RuntimeError(f"Mixamo export failed for {self.product_name}: {monitor}")

        return monitor.get("job_result")

    def download_animation(self, url):
        if not url:
            return

        response = session.get(url, timeout=120)
        response.raise_for_status()

        output_dir = self.path or os.getcwd()
        os.makedirs(output_dir, exist_ok=True)

        safe_name = self.product_name.replace("/", "-").replace(":", "-")
        output_path = os.path.join(output_dir, f"{safe_name}.fbx")
        with open(output_path, "wb") as file:
            file.write(response.content)

        self.log.emit(f"Saved {output_path}")
        self.current_task.emit(self.task)
        self.task += 1
