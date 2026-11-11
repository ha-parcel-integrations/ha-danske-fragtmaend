"""Sample Danske Fragtmænd API payloads shared by the test modules.

``registered_keyed`` and ``delivered_keyed`` are real keyed replies for one
consignment, before transit and after delivery, with every identifier and
personal field replaced. The in-transit and out-for-delivery samples are the
delivered reply cut back to the traces it had at that point.
"""

from __future__ import annotations

import copy
from typing import Any

ACTIVE_CODE = "FD000000"
DELIVERED_CODE = "FD111111"
KEY = "XyZ9"

_REGISTERED_KEYED: dict[str, Any] = {
    "ConsignmentNote": {
        "ConsignmentNumber": ACTIVE_CODE,
        "ConsignmentDate": "2026-11-11T00:00:00",
        "ShippingType": 4,
        "SenderReference": "00000000000000000000",
        "WhoPays": 1,
        "WhoPaysOriginal": 0,
        "Route": None,
        "Sender": {
            "Name": "Example Shop A/S",
            "Name2": None,
            "Name3": None,
            "Name4": None,
            "Street": "Example Street 1",
            "Street2": None,
            "Town": "Example Town",
            "Zipcode": "0000",
            "CustomerId": None,
            "Country": "DK",
            "Phone": "00000000",
            "Email": "shop@example.invalid",
            "ContactPerson": "Example Contact",
            "ContactPersonPhone": None,
        },
        "Receiver": {
            "Name": "Example Receiver",
            "Name2": None,
            "Name3": "",
            "Name4": None,
            "Street": "Example Road 2",
            "Street2": "",
            "Town": "Example City",
            "Zipcode": "9999",
            "CustomerId": "",
            "Country": "DK",
            "Phone": "11111111",
            "Email": "receiver@example.invalid",
            "ContactPerson": None,
            "ContactPersonPhone": None,
        },
        "Initiator": None,
        "Pickup": None,
        "PickupTime": None,
        "DeliveryTime": {
            "DotIntervalStart": None,
            "DotIntervalEnd": None,
            "ExpectedDeliveryDate": "2026-11-11T00:00:00",
            "ActualDeliveryDate": None,
            "RequestedDeliveryDate": "2026-11-11T21:00:00",
        },
        "Goods": [
            {
                "DId": 0,
                "FId": None,
                "NumberOfItems": 1,
                "Type": "PT1",
                "Description": "Not supplied",
                "Weight": 46,
                "Volume": 0,
                "Amount": None,
                "Length": None,
                "Width": None,
                "Height": None,
                "Stackable": None,
                "LoadMeters": None,
                "SenderRef": None,
                "DangerousGoods": [],
                "Products": [],
                "ColliCodes": [{"Id": 0, "FId": 0, "Barcode": "00000000000000000000"}],
            }
        ],
        "ServiceCodes": ["ADV", "FRIGIV:KTA", "FRIGIV:ANK", "PRI", "EML", "SMS", "TT+"],
        "BillingInfo": None,
        "ConsignmentNoteType": 0,
        "AgreementNumber": None,
        "Partner": None,
        "LastUpdated": "2026-11-09T14:42:30.79",
        "ExchangePallets": None,
        "Reference": None,
        "RedeliveryUrl": "",
        "ProductCode": "DayP",
    },
    "ConsignmentNoteTraces": [
        {
            "ConsignmentNumber": ACTIVE_CODE,
            "Status": 6,
            "Id": 0,
            "Date": "2026-11-09T14:42:30",
            "CargoHub": None,
            "Location": None,
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "DAT",
            "EventCodeText": "Vi har modtaget information om din forsendelse fra afsender.",
            "ExtentedEventCode": "DAT",
            "CargoHubDisplayText": "",
            "Username": "System",
            "Route": 0,
        }
    ],
    "ColliTraces": [
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 0,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 0,
            "Date": "0001-01-01T00:00:00",
            "CargoHub": None,
            "Location": None,
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "Unscanned",
            "EventCodeText": "ingen skanninger",
            "ExtentedEventCode": "Unscanned",
            "CargoHubDisplayText": None,
            "Username": None,
            "Route": 0,
        }
    ],
    "PictureList": [],
    "NotificationHistories": [
        {
            "ConsignmentNumber": ACTIVE_CODE,
            "Timestamp": "2026-11-09T14:42:31.6514331",
            "Receiver": "11111111",
            "Type": "sms",
            "EventCode": "DAT",
            "EventCodeDescriptionAsNotification": (
                "Vi har modtaget information om din forsendelse fra afsender."
            ),
        },
        {
            "ConsignmentNumber": ACTIVE_CODE,
            "Timestamp": "2026-11-09T14:42:31.6393524",
            "Receiver": "receiver@example.invalid",
            "Type": "email",
            "EventCode": "DAT",
            "EventCodeDescriptionAsNotification": (
                "Vi har modtaget information om din forsendelse fra afsender."
            ),
        },
    ],
    "EtaStatus": 0,
    "Key": {"Key": KEY},
    "ForcedColliScan": True,
    "State": "Klar",
    "Parent": None,
    "RelatedBillings": None,
    "RelatedBillingNumber": "",
    "Carrier": "Danske Fragtmænd",
    "Parcelshop": None,
    "ConsignmentComments": None,
}


_DELIVERED_KEYED: dict[str, Any] = {
    "ConsignmentNote": {
        "ConsignmentNumber": "FD000000",
        "ConsignmentDate": "2026-11-11T00:00:00",
        "ShippingType": 4,
        "SenderReference": "00000000000000000000",
        "WhoPays": 1,
        "WhoPaysOriginal": 0,
        "Route": None,
        "Sender": {
            "Name": "Example Shop A/S",
            "Name2": None,
            "Name3": None,
            "Name4": None,
            "Street": "",
            "Street2": None,
            "Town": "",
            "Zipcode": "0000",
            "CustomerId": None,
            "Country": "DK",
            "Phone": "",
            "Email": "",
            "ContactPerson": "",
            "ContactPersonPhone": None,
        },
        "Receiver": {
            "Name": "Example Receiver",
            "Name2": None,
            "Name3": "",
            "Name4": None,
            "Street": "Example Road 2",
            "Street2": "",
            "Town": "Example City",
            "Zipcode": "9999",
            "CustomerId": "",
            "Country": "DK",
            "Phone": "11111111",
            "Email": "receiver@example.invalid",
            "ContactPerson": None,
            "ContactPersonPhone": None,
        },
        "Initiator": None,
        "Pickup": None,
        "PickupTime": None,
        "DeliveryTime": {
            "DotIntervalStart": None,
            "DotIntervalEnd": None,
            "ExpectedDeliveryDate": "2026-11-12T00:00:00",
            "ActualDeliveryDate": None,
            "RequestedDeliveryDate": "2026-11-11T21:00:00",
        },
        "Goods": [
            {
                "DId": 1886458820,
                "FId": None,
                "NumberOfItems": 1,
                "Type": "PT1",
                "Description": "Not supplied",
                "Weight": 46,
                "Volume": 0,
                "Amount": None,
                "Length": None,
                "Width": None,
                "Height": None,
                "Stackable": None,
                "LoadMeters": None,
                "SenderRef": None,
                "DangerousGoods": [],
                "Products": [],
                "ColliCodes": [{"Id": 0, "FId": 0, "Barcode": "00000000000000000000"}],
            }
        ],
        "ServiceCodes": [
            "ADV",
            "FRIGIV:KTA",
            "FRIGIV:ANK",
            "PRI",
            "EML",
            "SMS",
            "TT+",
            "FRIGIVET",
        ],
        "BillingInfo": None,
        "ConsignmentNoteType": 0,
        "AgreementNumber": None,
        "Partner": None,
        "LastUpdated": "2026-11-11T11:13:09.607",
        "ExchangePallets": None,
        "Reference": None,
        "RedeliveryUrl": "",
        "ProductCode": "DayP",
    },
    "ConsignmentNoteTraces": [
        {
            "ConsignmentNumber": "FD000000",
            "Status": 3,
            "Id": 1290332583,
            "Date": "2026-11-11T11:13:09",
            "CargoHub": "PB",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "LEV",
            "EventCodeText": "Forsendelsen er leveret hos modtager.",
            "ExtentedEventCode": "LEV",
            "CargoHubDisplayText": "",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "ConsignmentNumber": "FD000000",
            "Status": 2,
            "Id": 1290203173,
            "Date": "2026-11-11T08:49:05",
            "CargoHub": "HA",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "OMX",
            "EventCodeText": "Forsendelsen er på vej fra Danske "
            "Fragtmænd Eksempelby til modtager.",
            "ExtentedEventCode": "OMX LEV",
            "CargoHubDisplayText": "",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "ConsignmentNumber": "FD000000",
            "Status": 2,
            "Id": 1290060118,
            "Date": "2026-11-11T06:37:27",
            "CargoHub": "HA",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "KTU",
            "EventCodeText": "Klar til udkørsel – vi forventer at "
            "levere forsendelsen i dag.",
            "ExtentedEventCode": "KTU",
            "CargoHubDisplayText": "",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "ConsignmentNumber": "FD000000",
            "Status": 2,
            "Id": 1289873875,
            "Date": "2026-11-11T01:49:51",
            "CargoHub": "PB",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "ANK",
            "EventCodeText": "Danske Fragtmænd Eksempelby behandler forsendelsen.",
            "ExtentedEventCode": "ANK",
            "CargoHubDisplayText": "",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "ConsignmentNumber": "FD000000",
            "Status": 6,
            "Id": 1288751862,
            "Date": "2026-11-09T14:42:30",
            "CargoHub": None,
            "Location": None,
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "DAT",
            "EventCodeText": "Vi har modtaget information om din "
            "forsendelse fra afsender.",
            "ExtentedEventCode": "DAT",
            "CargoHubDisplayText": "",
            "Username": "System",
            "Route": 0,
        },
    ],
    "ColliTraces": [
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 1,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 1290332580,
            "Date": "2026-11-11T11:11:41",
            "CargoHub": "PB",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "LEV",
            "EventCodeText": "Forsendelsen er leveret hos modtager.",
            "ExtentedEventCode": "LEV",
            "CargoHubDisplayText": "Danske Fragtmænd Eksempelby",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 2,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 1290203212,
            "Date": "2026-11-11T08:49:05",
            "CargoHub": "HA",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "OMX",
            "EventCodeText": "Forsendelsen er på vej fra Danske Fragtmænds "
            "terminal til modtager.",
            "ExtentedEventCode": "OMX LEV",
            "CargoHubDisplayText": "Danske Fragtmænd Eksempelby",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 1,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 1290060166,
            "Date": "2026-11-11T06:37:27",
            "CargoHub": "HA",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "KTU",
            "EventCodeText": "Klar til udkørsel – vi forventer at levere "
            "forsendelsen i dag.",
            "ExtentedEventCode": "KTU",
            "CargoHubDisplayText": "Danske Fragtmænd Eksempelby",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 1,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 1289873892,
            "Date": "2026-11-11T01:49:59",
            "CargoHub": "PB",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "ANK",
            "EventCodeText": "Danske Fragtmænds terminal behandler forsendelsen.",
            "ExtentedEventCode": "ANK",
            "CargoHubDisplayText": "Danske Fragtmænd Eksempelby",
            "Username": "10000001",
            "Route": 383,
        },
        {
            "Barcode": "00000000000000000000",
            "MarkAndNumber": None,
            "ScanAction": 1,
            "VehicleNo": None,
            "ExternalTrackingLink": None,
            "Id": 1289873872,
            "Date": "2026-11-11T01:49:50",
            "CargoHub": "PB",
            "Location": "",
            "Latitude": 0,
            "Longitude": 0,
            "EventCode": "ANK",
            "EventCodeText": "Danske Fragtmænds terminal behandler forsendelsen.",
            "ExtentedEventCode": "ANK",
            "CargoHubDisplayText": "Danske Fragtmænd Eksempelby",
            "Username": "10000001",
            "Route": 383,
        },
    ],
    "PictureList": [
        {
            "BookingNr": None,
            "ColliNr": None,
            "Id": 1,
            "Latitude": 0,
            "Longitude": 0,
            "TimestampClient": "2026-11-11T11:12:47",
            "TimestampServer": "2026-11-11T11:12:49.07",
            "UserName": "10000001",
            "Type": 0,
            "ConsignmentNumber": "FD000000",
        }
    ],
    "NotificationHistories": [
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T06:00:00",
            "Receiver": "11111111",
            "Type": "sms",
            "EventCode": "ANK",
            "EventCodeDescriptionAsNotification": "Danske Fragtmænds "
            "terminal behandler "
            "forsendelsen.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-09T14:42:31.6514331",
            "Receiver": "11111111",
            "Type": "sms",
            "EventCode": "DAT",
            "EventCodeDescriptionAsNotification": "Vi har modtaget "
            "information om din "
            "forsendelse fra "
            "afsender.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T11:13:08.5680269",
            "Receiver": "11111111",
            "Type": "sms",
            "EventCode": "LEV",
            "EventCodeDescriptionAsNotification": "Forsendelsen er "
            "leveret hos "
            "modtager.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T08:49:10.2623963",
            "Receiver": "11111111",
            "Type": "sms",
            "EventCode": "OMX LEV",
            "EventCodeDescriptionAsNotification": "Forsendelsen er på "
            "vej fra Danske "
            "Fragtmænds terminal "
            "til modtager.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T06:00:00",
            "Receiver": "receiver@example.invalid",
            "Type": "email",
            "EventCode": "ANK",
            "EventCodeDescriptionAsNotification": "Danske Fragtmænds "
            "terminal behandler "
            "forsendelsen.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-09T14:42:31.6393524",
            "Receiver": "receiver@example.invalid",
            "Type": "email",
            "EventCode": "DAT",
            "EventCodeDescriptionAsNotification": "Vi har modtaget "
            "information om din "
            "forsendelse fra "
            "afsender.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T11:13:08.5638634",
            "Receiver": "receiver@example.invalid",
            "Type": "email",
            "EventCode": "LEV",
            "EventCodeDescriptionAsNotification": "Forsendelsen er "
            "leveret hos "
            "modtager.",
        },
        {
            "ConsignmentNumber": "FD000000",
            "Timestamp": "2026-11-11T08:49:10.2569331",
            "Receiver": "receiver@example.invalid",
            "Type": "email",
            "EventCode": "OMX LEV",
            "EventCodeDescriptionAsNotification": "Forsendelsen er på "
            "vej fra Danske "
            "Fragtmænds terminal "
            "til modtager.",
        },
    ],
    "EtaStatus": 2,
    "Key": {"Key": KEY},
    "ForcedColliScan": True,
    "State": "Klar",
    "Parent": None,
    "RelatedBillings": None,
    "RelatedBillingNumber": "",
    "Carrier": "Danske Fragtmænd",
    "Parcelshop": None,
    "ConsignmentComments": None,
    "RedeliveryUrl": "",
}


def trace(
    status: int,
    date: str,
    event_code: str = "DAT",
    text: str | None = "Vi har modtaget information om din forsendelse fra afsender.",
    code: str = ACTIVE_CODE,
) -> dict[str, Any]:
    """One consignment trace row."""
    return {
        "ConsignmentNumber": code,
        "Status": status,
        "Id": 0,
        "Date": date,
        "CargoHub": None,
        "Location": None,
        "Latitude": 0,
        "Longitude": 0,
        "EventCode": event_code,
        "EventCodeText": text,
        "ExtentedEventCode": event_code,
        "CargoHubDisplayText": "",
        "Username": "System",
        "Route": 0,
    }


def _with_code(sample: dict[str, Any], code: str) -> dict[str, Any]:
    sample["ConsignmentNote"]["ConsignmentNumber"] = code
    for row in sample["ConsignmentNoteTraces"]:
        row["ConsignmentNumber"] = code
    for row in sample["NotificationHistories"] + sample["PictureList"]:
        row["ConsignmentNumber"] = code
    return sample


def registered_keyed(code: str = ACTIVE_CODE) -> dict[str, Any]:
    """The keyed reply before transit: one Status-6 ``DAT`` trace."""
    return _with_code(copy.deepcopy(_REGISTERED_KEYED), code)


def keyless(code: str = ACTIVE_CODE) -> dict[str, Any]:
    """The key-less reply: no parties, no key, no colli scans."""
    sample = registered_keyed(code)
    sample["ConsignmentNote"]["Sender"] = None
    sample["ConsignmentNote"]["Receiver"] = None
    sample["Key"] = None
    sample["ColliTraces"] = []
    sample["NotificationHistories"] = []
    return sample


def delivered_keyed(code: str = DELIVERED_CODE) -> dict[str, Any]:
    """The keyed reply after delivery: ``ANK``, ``KTU``, ``OMX``, then ``LEV``."""
    return _with_code(copy.deepcopy(_DELIVERED_KEYED), code)


def _cut_back(code: str, before: str) -> dict[str, Any]:
    sample = delivered_keyed(code)
    sample.pop("Key")
    for name in ("ConsignmentNoteTraces", "ColliTraces", "NotificationHistories"):
        stamp = "Timestamp" if name == "NotificationHistories" else "Date"
        sample[name] = [row for row in sample[name] if row[stamp] < before]
    sample["PictureList"] = []
    sample["ConsignmentNote"]["DeliveryTime"]["ExpectedDeliveryDate"] = (
        "2026-11-11T00:00:00"
    )
    return sample


def active_sample(code: str = ACTIVE_CODE) -> dict[str, Any]:
    """Under way and still at the hub (``KTU`` newest), echoed key removed."""
    return _cut_back(code, "2026-11-11T08:00:00")


def out_for_delivery_sample(code: str = ACTIVE_CODE) -> dict[str, Any]:
    """On its way to the receiver (``OMX`` newest), echoed key removed."""
    return _cut_back(code, "2026-11-11T11:00:00")


def delivered_sample(code: str = DELIVERED_CODE) -> dict[str, Any]:
    """The delivered reply as the client returns it, echoed key removed."""
    sample = delivered_keyed(code)
    sample.pop("Key")
    return sample


def pickup_sample(code: str = ACTIVE_CODE) -> dict[str, Any]:
    """An under-way consignment bound for a parcelshop."""
    sample = active_sample(code)
    sample["Parcelshop"] = {
        "Name": "Example Parcelshop",
        "Address": "Example Square 3",
        "Zipcode": "9999",
        "Cityname": "Example City",
    }
    return sample
