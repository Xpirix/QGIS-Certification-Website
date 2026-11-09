# coding=utf-8
"""Tools for Certification app."""
import base64
import hashlib
import hmac
import requests
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from django.conf import settings
from django.contrib.gis.serializers.geojson import Serializer
from django.urls import reverse
from urllib.parse import urlencode, quote, quote_plus

if TYPE_CHECKING:
    from certification.models import CertifyingOrganisation, TrainingCenter
    from django.contrib.gis.geos import GEOSGeometry


def check_slug(queryset, slug):
    """
    This function checks slug within a model queryset
    and return a new incremented slug when there are duplicates.

    """

    registered_slug = queryset.values_list('slug', flat=True)
    new_slug = slug
    if slug in registered_slug:
        match_slug = [s for s in registered_slug if slug in s]
        num = len(match_slug)
        new_slug = str(num) + '-' + slug

    return new_slug


class CustomSerializer(Serializer):
    """Custom serializer to return the name of the foreign key object."""

    def end_object(self, obj):
        for field in self.selected_fields:
            if field == 'pk':
                continue
            elif field in self._current.keys():
                continue
            else:
                try:
                    if '__' in field:
                        fields = field.split('__')
                        value = obj
                        for f in fields:
                            value = getattr(value, f)
                        if value != obj:
                            self._current[field] = value

                except AttributeError:
                    pass
        super(CustomSerializer, self).end_object(obj)


# Organisations whose marker goes at their second located training centre.
SECOND_CENTRE_ORGANISATIONS = {"qgis-qtibia-engineering"}


def marker_location(
    organisation: "CertifyingOrganisation", locations: list["GEOSGeometry"]
) -> "GEOSGeometry | None":
    """Pick where an organisation's marker goes on the world map.

    :param organisation: The organisation.
    :param locations: Locations of its training centres, oldest first.
    :returns: The first location, the second one for the organisations in
        ``SECOND_CENTRE_ORGANISATIONS`` when they have two, or None.
    """
    if not locations:
        return None
    if organisation.slug in SECOND_CENTRE_ORGANISATIONS and len(locations) > 1:
        return locations[1]
    return locations[0]


def world_map_data(
    organisations: Iterable["CertifyingOrganisation"],
) -> dict[str, dict[str, Any]]:
    """Group certifying organisations by country for the world map.

    An organisation has no location of its own, so its marker goes at one
    of its training centres, chosen by ``marker_location``. Without a located
    training centre it has no marker.

    :param organisations: Certifying organisations to place on the map.
    :returns: Count, links and marker position per two letter ISO country code.
    """
    # Imported here because the models import this module.
    from certification.models import TrainingCenter

    organisations = list(organisations)
    located: dict[int, list["GEOSGeometry"]] = {}
    for centre in (
        TrainingCenter.objects.filter(
            certifying_organisation__in=organisations, location__isnull=False
        )
        .order_by("pk")
        .only("certifying_organisation_id", "location")
    ):
        located.setdefault(centre.certifying_organisation_id, []).append(centre.location)

    data: dict[str, dict[str, Any]] = {}
    for organisation in organisations:
        location = marker_location(organisation, located.get(organisation.pk, []))
        entry = data.setdefault(
            organisation.country.code, {"count": 0, "organisations": []}
        )
        entry["count"] += 1
        entry["organisations"].append(
            {
                "name": organisation.name,
                "url": organisation.get_absolute_url(),
                "logo": organisation.logo.url if organisation.logo else None,
                "website": organisation.url or None,
                "slug": organisation.slug,
                "lon": location.x if location else None,
                "lat": location.y if location else None,
            }
        )
    return data


def training_center_map_data(
    training_centers: Iterable["TrainingCenter"],
    organisation: "CertifyingOrganisation",
) -> dict[str, Any]:
    """Describe the training centres of one organisation for its map.

    :param training_centers: Training centres to mark. Those without a
        location are left out.
    :param organisation: The organisation running them.
    :returns: The country, the organisation and one marker per centre.
    """
    return {
        "country": organisation.country.code,
        "organisation": organisation.name,
        "logo": organisation.logo.url if organisation.logo else None,
        "markers": [
            {
                "name": center.name,
                "lon": center.location.x,
                "lat": center.location.y,
                "address": center.address,
                "url": reverse(
                    "trainingcenter-detail",
                    kwargs={"organisation_slug": organisation.slug, "slug": center.slug},
                ),
            }
            for center in training_centers
            if center.location
        ],
    }


class PayrexxService:
    def __init__(self):
        self.instance_name = settings.PAYREXX_INSTANCE
        self.api_secret = settings.PAYREXX_API_SECRET
        self.base_url = "https://api.payrexx.com/v1.0/"

    def generate_signature(self, query_string):
        signature = hmac.new(self.api_secret.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256)
        return base64.b64encode(signature.digest()).decode('utf-8')

    def flatten_dict(self, dictionary, parent_key=''):
        flattened_data = {}
        for key, value in dictionary.items():
            new_key = f"{parent_key}[{key}]" if parent_key else key
            if isinstance(value, dict):
                flattened_data.update(self.flatten_dict(value, new_key))
            elif isinstance(value, list):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        flattened_data.update(self.flatten_dict(item, f"{new_key}[{i}]"))
                    else:
                        flattened_data[f"{new_key}[{i}]"] = item
            else:
                flattened_data[new_key] = value
        return flattened_data

    def encode_query_string(self, data):
        encoded_pairs = []
        for key, value in data.items():
            encoded_key = quote(key, safe='')
            if isinstance(value, list):
                for item in value:
                    encoded_pairs.append(f"{encoded_key}={quote(str(item), safe='')}")
            else:
                encoded_pairs.append(f"{encoded_key}={quote(str(value), safe='')}")
        return '&'.join(encoded_pairs)

    def prepare_data(self, raw_data):
        # Flatten the rawData
        data = self.flatten_dict(raw_data)

        # Create Query String
        query_string = urlencode(data, quote_via=quote_plus)

        # Generate the API Signature
        api_signature = self.generate_signature(query_string)

        # Add the API signature to the data payload
        data['ApiSignature'] = api_signature

        # Generate QueryString for the Request
        return self.encode_query_string(data)

    def create_gateway(
            self,
            reference_id,
            amount,
            currency,
            purpose,
            redirect_url,
            firstname: str = '',
            lastname: str = '',
            email: str = '',
            **kwargs
        ):
        """Create a payment gateway"""
        endpoint = "Gateway/"
        url = f"{self.base_url}{endpoint}?instance={self.instance_name}"

        amount = amount * 100  # Convert to cents
        raw_data = {
            'amount': str(amount),
            'currency': currency,
            'purpose': purpose,
            'successRedirectUrl': redirect_url,
            'fields': {
                'forename': {'value': firstname},
                'surname': {'value': lastname},
                'email': {'value': email}
            },
            'referenceId': str(reference_id),
        }

        # Generate QueryString for the Request
        request_query_string = self.prepare_data(raw_data)

        # Make the POST request
        response = requests.post(f"{url}", data=request_query_string)
        return response.json()

    def get_gateway(self, gateway_id):
        """Retrieve gateway information"""
        endpoint = f"Gateway/{gateway_id}/"
        url = f"{self.base_url}{endpoint}?instance={self.instance_name}"
        raw_data = {}
        # Generate QueryString for the Request
        request_query_string = self.prepare_data(raw_data)
        # Make the GET request
        response = requests.get(f"{url}", data=request_query_string)
        return response.json()

    def get_transaction(self, transaction_id):
        """Retrieve transaction information"""
        endpoint = f"Transaction/{transaction_id}/"
        url = f"{self.base_url}{endpoint}?instance={self.instance_name}"
        raw_data = {}
        # Generate QueryString for the Request
        request_query_string = self.prepare_data(raw_data)
        # Make the GET request
        response = requests.get(f"{url}", data=request_query_string)
        result = response.json()
        if result.get('status') == 'success':
            return result['data'][0]
        raise Exception(f"Error retrieving transaction: {result.get('message', 'Unknown error')}")
