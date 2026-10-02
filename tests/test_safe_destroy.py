"""Tests de scripts.safe_destroy (tareas 13.4, 13.5).

Property 3: terraform destroy nunca se ejecuta sin resultados en S3 (salvo force).
"""

import boto3
import pytest
from moto import mock_aws

import scripts.safe_destroy as sd
from scripts.safe_destroy import safe_destroy, s3_results_exist

CAL_ID = "CAL-20260115-001"
BUCKET = "test-pest-bucket"
MODULE = "IaC_terraform/ModeloPest/talabre-linux/us-east-1"


@mock_aws
def test_s3_results_exist_false_when_empty():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    assert s3_results_exist(BUCKET, CAL_ID) is False


@mock_aws
def test_s3_results_exist_true_with_object():
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    s3.put_object(Bucket=BUCKET, Key=f"calibrations/{CAL_ID}/modelo/result.hds", Body=b"x")
    assert s3_results_exist(BUCKET, CAL_ID) is True


@mock_aws
def test_aborts_without_results_and_no_force(mocker):
    """Property 3: sin resultados y force=False -> no se llama terraform destroy."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    tf = mocker.patch.object(sd, "_terraform_destroy")

    result = safe_destroy(CAL_ID, MODULE, BUCKET, force=False)

    assert result.success is False
    assert result.reason == "NO_RESULTS_IN_S3"
    tf.assert_not_called()


@mock_aws
def test_proceeds_with_results(mocker):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    s3.put_object(Bucket=BUCKET, Key=f"calibrations/{CAL_ID}/modelo/result.hds", Body=b"x")
    tf = mocker.patch.object(sd, "_terraform_destroy")

    result = safe_destroy(CAL_ID, MODULE, BUCKET, force=False)

    assert result.success is True
    tf.assert_called_once()


@mock_aws
def test_force_proceeds_without_results(mocker):
    """Req 9.8: force=True procede aunque no haya resultados."""
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    tf = mocker.patch.object(sd, "_terraform_destroy")

    result = safe_destroy(CAL_ID, MODULE, BUCKET, force=True)

    assert result.success is True
    tf.assert_called_once()


def test_invalid_calibration_id_rejected(mocker):
    tf = mocker.patch.object(sd, "_terraform_destroy")
    result = safe_destroy("not-an-id", MODULE, BUCKET, force=True)
    assert result.success is False
    assert result.reason == "INVALID_CALIBRATION_ID"
    tf.assert_not_called()


@mock_aws
def test_terraform_failure_reports_orphans(mocker):
    import subprocess

    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket=BUCKET)
    s3.put_object(Bucket=BUCKET, Key=f"calibrations/{CAL_ID}/modelo/r.hds", Body=b"x")
    mocker.patch.object(
        sd, "_terraform_destroy",
        side_effect=subprocess.CalledProcessError(1, "terraform destroy"),
    )
    mocker.patch.object(sd, "verify_no_orphan_resources", return_value=["q:job-1"])
    notify = mocker.patch.object(sd, "_notify")

    result = safe_destroy(CAL_ID, MODULE, BUCKET, force=False)

    assert result.success is False
    assert result.reason == "TERRAFORM_DESTROY_FAILED"
    assert result.orphans == ["q:job-1"]
    notify.assert_called_once()