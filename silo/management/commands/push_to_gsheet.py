import requests, json, logging
from requests.auth import HTTPDigestAuth

from django.core.mail import send_mail
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Q
from operator import and_, or_
from django.utils import timezone

from silo.models import Silo, Read, ReadType
from tola.util import siloToDict, combineColumns
from silo.gviews_v4 import export_to_gsheet_helper
logger = logging.getLogger("silo")

class Command(BaseCommand):
    """
    Usage: python manage.py push_to_gsheet --f weekly
    """
    help = 'Pushes all reads that have autopush checked and belong to a silo'

    def add_arguments(self, parser):
        parser.add_argument("-f", "--frequency", type=str, required=True)

    def handle(self, *args, **options):
        frequency = options['frequency']
        if frequency != "daily" and frequency != "weekly":
            return self.stdout.write("Frequency argument can either be 'daily' or 'weekly'")

        # Get all silos that have a unique field setup, have autopush frequency selected and autopush frequency is the same as specified in this command line argument.
        silos = Silo.objects.filter(unique_fields__isnull=False, reads__autopush_frequency__isnull=False, reads__autopush_frequency = frequency).distinct()
        readtypes = ReadType.objects.filter( Q(read_type__iexact="GSheet Import") | Q(read_type__iexact='Google Spreadsheet') )
        #readtypes = ReadType.objects.filter(reduce(or_, [Q(read_type__iexact="GSheet Import"), Q(read_type__iexact='Google Spreadsheet')] ))

        for silo in silos:
            reads = silo.reads.filter(reduce(or_, [Q(type=read.id) for read in readtypes])).filter(autopush_frequency__isnull=False, autopush_frequency = frequency)
            for read in reads:
                msgs = export_to_gsheet_helper(silo.owner, read.resource_id, silo.pk)
                for msg in msgs:
                    # if it is not a success message then I want to know
                    if msg.get("level") != 25:
                        # replace with logger
                        logger.error("silo_id=%s, read_id=%s, level: %s, msg: %s" % (silo.pk, read.pk, msg.get("level"), msg.get("msg")))
                        send_mail("Tola-Tables Auto-Pull Failed", "table_id: %s, source_id: %s, %s %s" % (silo.pk, read.pk, msg.get("level"), msg.get("msg")), "tolatables@mercycorps.org", [silo.owner.email], fail_silently=False)

        self.stdout.write("done executing gsheet export command job")