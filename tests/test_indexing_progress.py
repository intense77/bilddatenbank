import asyncio
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest
from fastapi import HTTPException, BackgroundTasks
from app.api.routes.archive import index_existing_folder, get_indexing_progress, IndexFolderRequest
from app.services.indexing_service import INDEXING_PROGRESS


def test_index_folder_synchronous_progress_init():
    async def _run():
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            (tmp_path / "test.jpg").touch()

            from app.services.indexing_service import update_indexing_progress
            # Reset indexing progress to simulate a finished prior job
            update_indexing_progress({
                "job_id": "old_job_123",
                "is_running": False,
                "finished": True,
                "percent": 100,
                "processed_count": 5,
                "pid": None,
            })

            mock_indexing = MagicMock()
            mock_indexing.index_folder.return_value = {"faces_detected": 0}
            mock_clustering = MagicMock()
            bg_tasks = BackgroundTasks()

            req = IndexFolderRequest(
                folder_path=str(tmp_path),
                recursive=True,
                force=False,
                cluster_faces=False,
            )

            with patch("subprocess.Popen") as mock_popen, patch("os.kill") as mock_kill:
                mock_proc = MagicMock()
                mock_proc.pid = 999999
                mock_popen.return_value = mock_proc
                mock_kill.return_value = None

                res = await index_existing_folder(request=req)

                # 1. Response must contain new job_id and status started
                assert res["status"] == "started"
                assert "job_id" in res
                new_job_id = res["job_id"]
                assert new_job_id != "old_job_123"

                # 2. Crucial: INDEXING_PROGRESS must be immediately is_running=True and finished=False
                assert INDEXING_PROGRESS["is_running"] is True
                assert INDEXING_PROGRESS["finished"] is False
                assert INDEXING_PROGRESS["job_id"] == new_job_id
                assert INDEXING_PROGRESS["percent"] == 0

                # 3. An immediate GET /index-progress must return is_running=True and the same job_id
                prog = await get_indexing_progress()
                assert prog["is_running"] is True
                assert prog["finished"] is False
                assert prog["job_id"] == new_job_id

                # 4. Starting another indexing while running must return 409
                with pytest.raises(HTTPException) as exc_info:
                    await index_existing_folder(request=req)
                assert exc_info.value.status_code == 409

            # Cleanup state for following tests
            INDEXING_PROGRESS.update({
                "job_id": None,
                "is_running": False,
                "finished": False,
            })

    asyncio.run(_run())
