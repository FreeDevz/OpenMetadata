import logging
import os
import uuid
from typing import Iterable

import boto3

from metadata.generated.schema.api.services.createStorageService import (
    CreateStorageServiceEntityRequest,
)
from metadata.generated.schema.type.entityReference import EntityReference
from metadata.generated.schema.type.storage import StorageServiceType
from metadata.ingestion.api.common import ConfigModel, Record, WorkflowContext
from metadata.ingestion.api.source import Source, SourceStatus
from metadata.ingestion.ometa.ometa_api import OpenMetadata
from metadata.ingestion.ometa.openmetadata_rest import MetadataServerConfig
from metadata.generated.schema.entity.data.location import Location, LocationType
from metadata.generated.schema.entity.services.storageService import StorageService

logger: logging.Logger = logging.getLogger(__name__)


class S3SourceConfig(ConfigModel):
    service_name: str = ""
    aws_access_key_id: str
    aws_secret_access_key: str


class S3Source(Source):
    config: S3SourceConfig
    status: SourceStatus

    def __init__(
        self, config: S3SourceConfig, metadata_config: MetadataServerConfig, ctx
    ):
        super().__init__(ctx)
        self.config = config
        self.metadata_config = metadata_config
        os.environ["AWS_ACCESS_KEY_ID"] = self.config.aws_access_key_id
        os.environ["AWS_SECRET_ACCESS_KEY"] = self.config.aws_secret_access_key
        self.status = SourceStatus()
        self.service = get_storage_service_or_create(
            config.service_name, metadata_config
        )
        self.s3 = boto3.resource("s3")

    @classmethod
    def create(
        cls, config_dict: dict, metadata_config_dict: dict, ctx: WorkflowContext
    ):
        config = S3SourceConfig.parse_obj(config_dict)
        metadata_config = MetadataServerConfig.parse_obj(metadata_config_dict)
        return cls(config, metadata_config, ctx)

    def prepare(self):
        pass

    def next_record(self) -> Iterable[Record]:
        try:
            for bucket in self.s3.buckets.all():
                self.status.scanned(bucket.name)
                yield Location(
                    id=uuid.uuid4(),
                    name=bucket.name,
                    displayName=bucket.name,
                    locationType=LocationType.Bucket,
                    service=EntityReference(id=self.service.id, type="storageService"),
                )
        except Exception as e:
            self.status.failure("error", str(e))

    def get_status(self) -> SourceStatus:
        return self.status


def get_storage_service_or_create(
    service_name: str, metadata_config: MetadataServerConfig
) -> StorageService:
    metadata = OpenMetadata(metadata_config)
    service = metadata.get_by_name(entity=StorageService, fqdn=service_name)
    if service is not None:
        return service
    return metadata.create_or_update(
        CreateStorageServiceEntityRequest(
            name=service_name,
            serviceType=StorageServiceType.S3,
        )
    )
