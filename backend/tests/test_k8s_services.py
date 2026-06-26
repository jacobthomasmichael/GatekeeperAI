"""
Unit tests for the three Kubernetes service modules:
  - k8s_ingress_service: write_app_ingress, remove_app_ingress
  - k8s_build_service: _create_context_tar, _wait_for_job, build_and_push
  - k8s_app_service: deploy_app, stop_app, start_app, get_app_logs, get_app_status, delete_app

All tests mock the kubernetes client — no real cluster required.
"""
import base64
import os
import tarfile
import tempfile
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest
from kubernetes.client.exceptions import ApiException


# ── Helpers ───────────────────────────────────────────────────────────────────

def _api_exception(status: int) -> ApiException:
    e = ApiException(status=status)
    e.status = status
    return e


def _patch_k8s_config():
    """Return a patcher that makes _load_k8s_config() succeed via in-cluster path."""
    return patch("kubernetes.config.load_incluster_config")


# ── k8s_ingress_service ───────────────────────────────────────────────────────

class TestWriteAppIngress:
    def test_creates_service_and_ingress_when_not_exist(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_core = mock_core_cls.return_value
            mock_net = mock_net_cls.return_value
            # 404 → create path for both
            mock_core.read_namespaced_service.side_effect = _api_exception(404)
            mock_net.read_namespaced_ingress.side_effect = _api_exception(404)

            from app.services.k8s_ingress_service import write_app_ingress
            write_app_ingress("my-app", 8080, "https://gk.example.com")

            mock_core.create_namespaced_service.assert_called_once()
            mock_net.create_namespaced_ingress.assert_called_once()
            mock_core.replace_namespaced_service.assert_not_called()
            mock_net.replace_namespaced_ingress.assert_not_called()

    def test_updates_service_and_ingress_when_exist(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_core = mock_core_cls.return_value
            mock_net = mock_net_cls.return_value
            mock_core.read_namespaced_service.return_value = MagicMock()
            mock_net.read_namespaced_ingress.return_value = MagicMock()

            from app.services.k8s_ingress_service import write_app_ingress
            write_app_ingress("my-app", 8080, "https://gk.example.com")

            mock_core.replace_namespaced_service.assert_called_once()
            mock_net.replace_namespaced_ingress.assert_called_once()
            mock_core.create_namespaced_service.assert_not_called()
            mock_net.create_namespaced_ingress.assert_not_called()

    def test_private_app_has_auth_annotations(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_core = mock_core_cls.return_value
            mock_net = mock_net_cls.return_value
            mock_core.read_namespaced_service.side_effect = _api_exception(404)
            mock_net.read_namespaced_ingress.side_effect = _api_exception(404)

            from app.services.k8s_ingress_service import write_app_ingress
            write_app_ingress("my-app", 8080, "https://gk.example.com", visibility="private")

            ingress_body = mock_net.create_namespaced_ingress.call_args[0][1]
            annotations = ingress_body.metadata.annotations
            assert "nginx.ingress.kubernetes.io/auth-url" in annotations
            assert "nginx.ingress.kubernetes.io/auth-signin" in annotations
            assert "my-app" in annotations["nginx.ingress.kubernetes.io/auth-url"]

    def test_public_app_omits_auth_annotations(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_core = mock_core_cls.return_value
            mock_net = mock_net_cls.return_value
            mock_core.read_namespaced_service.side_effect = _api_exception(404)
            mock_net.read_namespaced_ingress.side_effect = _api_exception(404)

            from app.services.k8s_ingress_service import write_app_ingress
            write_app_ingress("my-app", 8080, "https://gk.example.com", visibility="public")

            ingress_body = mock_net.create_namespaced_ingress.call_args[0][1]
            annotations = ingress_body.metadata.annotations
            assert "nginx.ingress.kubernetes.io/auth-url" not in annotations

    def test_non_404_service_exception_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api"):

            mock_core = mock_core_cls.return_value
            mock_core.read_namespaced_service.side_effect = _api_exception(500)

            from app.services.k8s_ingress_service import write_app_ingress
            with pytest.raises(ApiException):
                write_app_ingress("my-app", 8080, "https://gk.example.com")

    def test_non_404_ingress_exception_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_core = mock_core_cls.return_value
            mock_net = mock_net_cls.return_value
            mock_core.read_namespaced_service.return_value = MagicMock()
            mock_net.read_namespaced_ingress.side_effect = _api_exception(500)

            from app.services.k8s_ingress_service import write_app_ingress
            with pytest.raises(ApiException):
                write_app_ingress("my-app", 8080, "https://gk.example.com")


class TestRemoveAppIngress:
    def test_deletes_ingress_and_service(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            from app.services.k8s_ingress_service import remove_app_ingress
            remove_app_ingress("my-app")

            mock_net_cls.return_value.delete_namespaced_ingress.assert_called_once()
            mock_core_cls.return_value.delete_namespaced_service.assert_called_once()

    def test_404_on_delete_is_silently_ignored(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_net_cls.return_value.delete_namespaced_ingress.side_effect = _api_exception(404)
            mock_core_cls.return_value.delete_namespaced_service.side_effect = _api_exception(404)

            from app.services.k8s_ingress_service import remove_app_ingress
            remove_app_ingress("my-app")  # must not raise

    def test_non_404_on_delete_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.NetworkingV1Api") as mock_net_cls:

            mock_net_cls.return_value.delete_namespaced_ingress.side_effect = _api_exception(500)

            from app.services.k8s_ingress_service import remove_app_ingress
            with pytest.raises(ApiException):
                remove_app_ingress("my-app")


# ── k8s_build_service ─────────────────────────────────────────────────────────

class TestCreateContextTar:
    def test_creates_valid_targz(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a dummy file in the build dir
            (open(os.path.join(tmpdir, "Dockerfile"), "w")).write("FROM python:3.11")

            from app.services.k8s_build_service import _create_context_tar
            tar_path = _create_context_tar(tmpdir)
            try:
                assert os.path.exists(tar_path)
                assert tarfile.is_tarfile(tar_path)
                with tarfile.open(tar_path, "r:gz") as tf:
                    names = tf.getnames()
                assert any("Dockerfile" in n for n in names)
            finally:
                os.unlink(tar_path)


class TestWaitForJob:
    def test_returns_when_succeeded(self):
        mock_batch = MagicMock()
        job_status = MagicMock()
        job_status.status.succeeded = 1
        job_status.status.failed = None
        mock_batch.read_namespaced_job_status.return_value = job_status

        from app.services.k8s_build_service import _wait_for_job
        _wait_for_job(mock_batch, "build-job", "gatekeeperai-builds")
        mock_batch.read_namespaced_job_status.assert_called_once()

    def test_raises_on_failed_job(self):
        mock_batch = MagicMock()
        job_status = MagicMock()
        job_status.status.succeeded = None
        job_status.status.failed = 1
        mock_batch.read_namespaced_job_status.return_value = job_status

        from app.services.k8s_build_service import _wait_for_job
        with pytest.raises(RuntimeError, match="failed"):
            _wait_for_job(mock_batch, "build-job", "gatekeeperai-builds")

    def test_raises_timeout_when_deadline_exceeded(self):
        mock_batch = MagicMock()
        job_status = MagicMock()
        job_status.status.succeeded = None
        job_status.status.failed = None
        mock_batch.read_namespaced_job_status.return_value = job_status

        import app.services.k8s_build_service as svc
        with patch.object(svc, "BUILD_TIMEOUT_SECONDS", -1):
            from app.services.k8s_build_service import _wait_for_job
            with pytest.raises(TimeoutError):
                _wait_for_job(mock_batch, "build-job", "gatekeeperai-builds")


class TestBuildAndPush:
    def test_returns_correct_image_uri(self):
        with tempfile.TemporaryDirectory() as build_dir, \
             _patch_k8s_config(), \
             patch("boto3.client") as mock_boto, \
             patch("kubernetes.client.BatchV1Api") as mock_batch_cls, \
             patch("app.services.k8s_build_service.settings") as mock_settings:

            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.BUILD_CONTEXT_BUCKET = "gk-builds"

            mock_batch = mock_batch_cls.return_value
            job_status = MagicMock()
            job_status.status.succeeded = 1
            job_status.status.failed = None
            mock_batch.read_namespaced_job_status.return_value = job_status

            from app.services.k8s_build_service import build_and_push
            uri = build_and_push(build_dir, "my-app", "123.dkr.ecr.us-east-1.amazonaws.com", "abc123def456")

            assert uri.startswith("123.dkr.ecr.us-east-1.amazonaws.com/gatekeeperai-apps/my-app:")
            assert "abc123def4" in uri  # first 12 chars of commit sha
            mock_boto.return_value.upload_file.assert_called_once()
            mock_batch.create_namespaced_job.assert_called_once()

    def test_cleans_up_tar_on_s3_error(self):
        """Temp tar file must be deleted even if the S3 upload fails."""
        created_tars = []

        def track_tar(build_dir):
            path = original_create_tar(build_dir)
            created_tars.append(path)
            return path

        with tempfile.TemporaryDirectory() as build_dir, \
             _patch_k8s_config(), \
             patch("boto3.client") as mock_boto, \
             patch("app.services.k8s_build_service.settings") as mock_settings:

            mock_settings.AWS_REGION = "us-east-1"
            mock_settings.BUILD_CONTEXT_BUCKET = "gk-builds"
            mock_boto.return_value.upload_file.side_effect = Exception("S3 error")

            import app.services.k8s_build_service as svc
            original_create_tar = svc._create_context_tar
            with patch.object(svc, "_create_context_tar", side_effect=track_tar):
                from app.services.k8s_build_service import build_and_push
                with pytest.raises(Exception, match="S3 error"):
                    build_and_push(build_dir, "my-app", "123.dkr.ecr.us-east-1.amazonaws.com", "abc123")

            # All created tars must be cleaned up
            for tar_path in created_tars:
                assert not os.path.exists(tar_path), f"Temp tar not cleaned up: {tar_path}"


# ── k8s_app_service ───────────────────────────────────────────────────────────

class TestDeployApp:
    def test_creates_secret_and_deployment_when_not_exist(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_core = mock_core_cls.return_value
            mock_apps = mock_apps_cls.return_value
            mock_core.read_namespaced_secret.side_effect = _api_exception(404)
            mock_apps.read_namespaced_deployment.side_effect = _api_exception(404)

            from app.services.k8s_app_service import deploy_app
            result = deploy_app("my-app", "123.dkr.ecr.amazonaws.com/app:tag", 8080, {"KEY": "val"})

            mock_core.create_namespaced_secret.assert_called_once()
            mock_apps.create_namespaced_deployment.assert_called_once()
            assert result == "gk-app-my-app"

    def test_updates_secret_and_deployment_when_exist(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_core = mock_core_cls.return_value
            mock_apps = mock_apps_cls.return_value
            mock_core.read_namespaced_secret.return_value = MagicMock()
            mock_apps.read_namespaced_deployment.return_value = MagicMock()

            from app.services.k8s_app_service import deploy_app
            deploy_app("my-app", "123.dkr.ecr.amazonaws.com/app:tag", 8080, {"KEY": "val"})

            mock_core.replace_namespaced_secret.assert_called_once()
            mock_apps.replace_namespaced_deployment.assert_called_once()

    def test_env_vars_are_base64_encoded_in_secret(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_core = mock_core_cls.return_value
            mock_apps = mock_apps_cls.return_value
            mock_core.read_namespaced_secret.side_effect = _api_exception(404)
            mock_apps.read_namespaced_deployment.side_effect = _api_exception(404)

            from app.services.k8s_app_service import deploy_app
            deploy_app("my-app", "image:tag", 8080, {"MY_SECRET": "supersecret"})

            secret_body = mock_core.create_namespaced_secret.call_args[0][1]
            encoded = secret_body.data["MY_SECRET"]
            assert base64.b64decode(encoded).decode() == "supersecret"

    def test_non_404_exception_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api"):

            mock_core_cls.return_value.read_namespaced_secret.side_effect = _api_exception(500)

            from app.services.k8s_app_service import deploy_app
            with pytest.raises(ApiException):
                deploy_app("my-app", "image:tag", 8080, {})


class TestStopStartApp:
    def test_stop_app_scales_to_zero(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            from app.services.k8s_app_service import stop_app
            stop_app("my-app")

            mock_apps_cls.return_value.patch_namespaced_deployment.assert_called_once_with(
                "gk-app-my-app", "gatekeeperai-apps", {"spec": {"replicas": 0}}
            )

    def test_start_app_scales_to_one(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            from app.services.k8s_app_service import start_app
            start_app("my-app")

            mock_apps_cls.return_value.patch_namespaced_deployment.assert_called_once_with(
                "gk-app-my-app", "gatekeeperai-apps", {"spec": {"replicas": 1}}
            )

    def test_stop_404_is_ignored(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.patch_namespaced_deployment.side_effect = _api_exception(404)
            from app.services.k8s_app_service import stop_app
            stop_app("my-app")  # must not raise

    def test_stop_non_404_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.patch_namespaced_deployment.side_effect = _api_exception(500)
            from app.services.k8s_app_service import stop_app
            with pytest.raises(ApiException):
                stop_app("my-app")


class TestGetAppLogs:
    def test_returns_no_pods_message_when_empty(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls:

            mock_core_cls.return_value.list_namespaced_pod.return_value.items = []

            from app.services.k8s_app_service import get_app_logs
            result = get_app_logs("my-app")
            assert result == "No running pods found."

    def test_returns_log_string_from_most_recent_pod(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls:

            mock_core = mock_core_cls.return_value
            pod = MagicMock()
            pod.metadata.name = "gk-app-my-app-abc12"
            pod.metadata.creation_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            mock_core.list_namespaced_pod.return_value.items = [pod]
            mock_core.read_namespaced_pod_log.return_value = "log output here"

            from app.services.k8s_app_service import get_app_logs
            result = get_app_logs("my-app")
            assert result == "log output here"

    def test_returns_error_message_on_api_exception(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls:

            mock_core = mock_core_cls.return_value
            pod = MagicMock()
            pod.metadata.name = "gk-app-my-app-abc12"
            pod.metadata.creation_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
            mock_core.list_namespaced_pod.return_value.items = [pod]
            mock_core.read_namespaced_pod_log.side_effect = _api_exception(500)

            from app.services.k8s_app_service import get_app_logs
            result = get_app_logs("my-app")
            assert result == "Unable to retrieve logs."


class TestGetAppStatus:
    def test_returns_ready_status(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            d = MagicMock()
            d.status.ready_replicas = 1
            d.status.replicas = 1
            mock_apps_cls.return_value.read_namespaced_deployment_status.return_value = d

            from app.services.k8s_app_service import get_app_status
            result = get_app_status("my-app")
            assert result == {"ready_replicas": 1, "total_replicas": 1, "available": True}

    def test_returns_zeros_when_not_found(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.read_namespaced_deployment_status.side_effect = _api_exception(404)

            from app.services.k8s_app_service import get_app_status
            result = get_app_status("my-app")
            assert result == {"ready_replicas": 0, "total_replicas": 0, "available": False}

    def test_non_404_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.read_namespaced_deployment_status.side_effect = _api_exception(500)

            from app.services.k8s_app_service import get_app_status
            with pytest.raises(ApiException):
                get_app_status("my-app")

    def test_available_false_when_zero_ready(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            d = MagicMock()
            d.status.ready_replicas = None
            d.status.replicas = 1
            mock_apps_cls.return_value.read_namespaced_deployment_status.return_value = d

            from app.services.k8s_app_service import get_app_status
            result = get_app_status("my-app")
            assert result["available"] is False


class TestDeleteApp:
    def test_deletes_deployment_and_secret(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            from app.services.k8s_app_service import delete_app
            delete_app("my-app")

            mock_apps_cls.return_value.delete_namespaced_deployment.assert_called_once_with(
                "gk-app-my-app", "gatekeeperai-apps"
            )
            mock_core_cls.return_value.delete_namespaced_secret.assert_called_once_with(
                "gk-app-my-app-secrets", "gatekeeperai-apps"
            )

    def test_404_on_delete_is_ignored(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.delete_namespaced_deployment.side_effect = _api_exception(404)
            mock_core_cls.return_value.delete_namespaced_secret.side_effect = _api_exception(404)

            from app.services.k8s_app_service import delete_app
            delete_app("my-app")  # must not raise

    def test_non_404_propagates(self):
        with _patch_k8s_config(), \
             patch("kubernetes.client.CoreV1Api") as mock_core_cls, \
             patch("kubernetes.client.AppsV1Api") as mock_apps_cls:

            mock_apps_cls.return_value.delete_namespaced_deployment.side_effect = _api_exception(500)

            from app.services.k8s_app_service import delete_app
            with pytest.raises(ApiException):
                delete_app("my-app")
