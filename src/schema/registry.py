import json
import logging
from typing import Dict, Any, Optional, List
from enum import Enum
from dataclasses import dataclass
import hashlib

logger = logging.getLogger(__name__)

class SchemaFormat(Enum):
    AVRO = "avro"
    JSON_SCHEMA = "json_schema"
    PROTOBUF = "protobuf"

@dataclass
class SchemaVersion:
    schema_id: int
    version: int
    schema_str: str
    schema_format: SchemaFormat
    compatibility: str = "BACKWARD"  # BACKWARD, FORWARD, FULL, NONE
    
    def get_fingerprint(self) -> str:
        return hashlib.sha256(self.schema_str.encode()).hexdigest()[:16]

# Transaction Schema (JSON Schema format)
TRANSACTION_SCHEMA_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FraudDetectionTransaction",
    "description": "Schema for fraud detection transaction events",
    "type": "object",
    "required": [
        "transaction_id",
        "user_id",
        "timestamp",
        "amount",
        "currency",
        "location"
    ],
    "properties": {
        "transaction_id": {
            "type": "string",
            "description": "Unique transaction identifier",
            "pattern": "^[a-zA-Z0-9-]+$"
        },
        "user_id": {
            "type": "integer",
            "description": "User identifier",
            "minimum": 1
        },
        "card_number": {
            "type": "string",
            "description": "Masked card number",
            "pattern": "^[0-9]{4}-[0-9]{4}-[0-9]{4}-[0-9]{4}$"
        },
        "timestamp": {
            "type": "number",
            "description": "Unix timestamp of transaction",
            "minimum": 0
        },
        "amount": {
            "type": "number",
            "description": "Transaction amount",
            "minimum": 0
        },
        "currency": {
            "type": "string",
            "description": "ISO 4217 currency code",
            "pattern": "^[A-Z]{3}$"
        },
        "merchant_id": {
            "type": "integer",
            "description": "Merchant identifier",
            "minimum": 1
        },
        "location": {
            "type": "object",
            "required": ["lat", "lon", "city", "country"],
            "properties": {
                "lat": {
                    "type": "number",
                    "description": "Latitude",
                    "minimum": -90,
                    "maximum": 90
                },
                "lon": {
                    "type": "number",
                    "description": "Longitude",
                    "minimum": -180,
                    "maximum": 180
                },
                "city": {
                    "type": "string",
                    "description": "City name"
                },
                "country": {
                    "type": "string",
                    "description": "Country name"
                }
            }
        },
        "metadata": {
            "type": "object",
            "description": "Additional transaction metadata",
            "additionalProperties": True
        }
    },
    "additionalProperties": False
}

# Fraud Alert Schema
FRAUD_ALERT_SCHEMA_V1 = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "FraudAlert",
    "description": "Schema for fraud detection alerts",
    "type": "object",
    "required": [
        "alert_id",
        "transaction_id",
        "user_id",
        "rule_name",
        "risk_score",
        "timestamp"
    ],
    "properties": {
        "alert_id": {
            "type": "string",
            "description": "Unique alert identifier"
        },
        "transaction_id": {
            "type": "string",
            "description": "Related transaction ID"
        },
        "user_id": {
            "type": "integer",
            "description": "User identifier"
        },
        "rule_name": {
            "type": "string",
            "description": "Detection rule that triggered alert"
        },
        "reason": {
            "type": "string",
            "description": "Human-readable reason for alert"
        },
        "risk_score": {
            "type": "number",
            "description": "Risk score (0.0 to 1.0)",
            "minimum": 0.0,
            "maximum": 1.0
        },
        "timestamp": {
            "type": "number",
            "description": "Alert generation timestamp"
        },
        "metadata": {
            "type": "object",
            "description": "Additional alert metadata"
        }
    }
}

# Avro Schema for Transactions
TRANSACTION_AVRO_SCHEMA = {
    "type": "record",
    "name": "Transaction",
    "namespace": "com.fraud.detection",
    "doc": "Transaction event for fraud detection",
    "fields": [
        {"name": "transaction_id", "type": "string", "doc": "Unique transaction identifier"},
        {"name": "user_id", "type": "int", "doc": "User identifier"},
        {"name": "card_number", "type": ["null", "string"], "default": None, "doc": "Masked card number"},
        {"name": "timestamp", "type": "double", "doc": "Unix timestamp"},
        {"name": "amount", "type": "double", "doc": "Transaction amount"},
        {"name": "currency", "type": "string", "doc": "Currency code"},
        {"name": "merchant_id", "type": "int", "doc": "Merchant identifier"},
        {
            "name": "location",
            "type": {
                "type": "record",
                "name": "Location",
                "fields": [
                    {"name": "lat", "type": "double", "doc": "Latitude"},
                    {"name": "lon", "type": "double", "doc": "Longitude"},
                    {"name": "city", "type": "string", "doc": "City"},
                    {"name": "country", "type": "string", "doc": "Country"}
                ]
            }
        },
        {
            "name": "metadata",
            "type": ["null", {"type": "map", "values": "string"}],
            "default": None,
            "doc": "Additional metadata"
        }
    ]
}

class SchemaValidator:
    def __init__(self):
        self.schemas: Dict[str, Dict[str, Any]] = {
            "transaction.v1": TRANSACTION_SCHEMA_V1,
            "fraud_alert.v1": FRAUD_ALERT_SCHEMA_V1
        }
        self.logger = logging.getLogger(__name__)
    
    def register_schema(self, schema_name: str, schema: Dict[str, Any]) -> bool:
        try:
            self.schemas[schema_name] = schema
            self.logger.info(f"Registered schema: {schema_name}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register schema {schema_name}: {e}")
            return False
    
    def validate(self, data: Dict[str, Any], schema_name: str) -> tuple[bool, Optional[str]]:
        if schema_name not in self.schemas:
            return False, f"Schema not found: {schema_name}"
        
        schema = self.schemas[schema_name]
        
        try:
            self._validate_object(data, schema)
            return True, None
        except Exception as e:
            return False, str(e)
    
    def _validate_object(self, data: Dict[str, Any], schema: Dict[str, Any]):
        # Check required fields
        required = schema.get("required", [])
        for field in required:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")
        
        # Check field types
        properties = schema.get("properties", {})
        for field, value in data.items():
            if field not in properties:
                if not schema.get("additionalProperties", True):
                    raise ValueError(f"Unexpected field: {field}")
                continue
            
            field_schema = properties[field]
            self._validate_field(value, field_schema, field)
    
    def _validate_field(self, value: Any, field_schema: Dict[str, Any], field_name: str):
        expected_type = field_schema.get("type")
        
        if expected_type == "string" and not isinstance(value, str):
            raise ValueError(f"Field {field_name} must be string, got {type(value)}")
        
        if expected_type == "integer" and not isinstance(value, int):
            raise ValueError(f"Field {field_name} must be integer, got {type(value)}")
        
        if expected_type == "number" and not isinstance(value, (int, float)):
            raise ValueError(f"Field {field_name} must be number, got {type(value)}")
        
        if expected_type == "object" and isinstance(value, dict):
            self._validate_object(value, field_schema)
        
        # Check pattern if specified
        if "pattern" in field_schema and isinstance(value, str):
            import re
            if not re.match(field_schema["pattern"], value):
                raise ValueError(f"Field {field_name} does not match pattern: {field_schema['pattern']}")
        
        # Check range constraints
        if "minimum" in field_schema and isinstance(value, (int, float)):
            if value < field_schema["minimum"]:
                raise ValueError(f"Field {field_name} below minimum: {field_schema['minimum']}")
        
        if "maximum" in field_schema and isinstance(value, (int, float)):
            if value > field_schema["maximum"]:
                raise ValueError(f"Field {field_name} above maximum: {field_schema['maximum']}")
    
    def get_schema(self, schema_name: str) -> Optional[Dict[str, Any]]:
        return self.schemas.get(schema_name)
    
    def list_schemas(self) -> List[str]:
        return list(self.schemas.keys())

class SchemaRegistry:
    def __init__(self):
        self.versions: Dict[str, List[SchemaVersion]] = {}
        self.validator = SchemaValidator()
        self.logger = logging.getLogger(__name__)
        self._next_id = 1
        
        # Register default schemas
        self._register_default_schemas()
    
    def _register_default_schemas(self):
        self.register_schema(
            subject="transaction",
            schema_str=json.dumps(TRANSACTION_SCHEMA_V1),
            schema_format=SchemaFormat.JSON_SCHEMA
        )
        
        self.register_schema(
            subject="fraud_alert",
            schema_str=json.dumps(FRAUD_ALERT_SCHEMA_V1),
            schema_format=SchemaFormat.JSON_SCHEMA
        )
    
    def register_schema(
        self,
        subject: str,
        schema_str: str,
        schema_format: SchemaFormat = SchemaFormat.JSON_SCHEMA,
        compatibility: str = "BACKWARD"
    ) -> int:
        if subject not in self.versions:
            self.versions[subject] = []
        
        version = len(self.versions[subject]) + 1
        schema_id = self._next_id
        self._next_id += 1
        
        schema_version = SchemaVersion(
            schema_id=schema_id,
            version=version,
            schema_str=schema_str,
            schema_format=schema_format,
            compatibility=compatibility
        )
        
        self.versions[subject].append(schema_version)
        self.logger.info(f"Registered schema {subject} v{version} with ID {schema_id}")
        
        return schema_id
    
    def get_latest_schema(self, subject: str) -> Optional[SchemaVersion]:
        if subject not in self.versions or not self.versions[subject]:
            return None
        return self.versions[subject][-1]
    
    def get_schema_by_id(self, schema_id: int) -> Optional[SchemaVersion]:
        for versions in self.versions.values():
            for schema in versions:
                if schema.schema_id == schema_id:
                    return schema
        return None
    
    def check_compatibility(
        self,
        subject: str,
        new_schema_str: str
    ) -> tuple[bool, Optional[str]]:
        latest = self.get_latest_schema(subject)
        if not latest:
            return True, None  # First schema is always compatible
        
        # For JSON Schema, check backward compatibility
        # (new schema can read data written with old schema)
        try:
            old_schema = json.loads(latest.schema_str)
            new_schema = json.loads(new_schema_str)
            
            # Check if all required fields in old schema exist in new schema
            old_required = set(old_schema.get("required", []))
            new_required = set(new_schema.get("required", []))
            
            # New schema shouldn't add new required fields (BACKWARD compatibility)
            added_required = new_required - old_required
            if added_required:
                return False, f"New required fields added: {added_required}"
            
            return True, None
            
        except Exception as e:
            return False, f"Compatibility check failed: {e}"
