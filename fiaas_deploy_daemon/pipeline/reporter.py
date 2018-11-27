#!/usr/bin/env python
# -*- coding: utf-8
from __future__ import absolute_import

import logging
import posixpath

from blinker import signal

from fiaas_deploy_daemon.log_extras import get_final_logs
from ..deployer.bookkeeper import DEPLOY_FAILED, DEPLOY_STARTED, DEPLOY_SUCCESS


class Reporter(object):
    """Report results of deployments to pipeline"""
    def __init__(self, config, session):
        self._environment = config.environment
        self._infrastructure = config.infrastructure
        self._session = session
        self._callback_urls = {}
        self._logger = logging.getLogger(__name__)
        signal(DEPLOY_STARTED).connect(self._handle_started)
        signal(DEPLOY_SUCCESS).connect(self._handle_success)
        signal(DEPLOY_FAILED).connect(self._handle_failure)

    def register(self, app_spec, url):
        self._callback_urls[(app_spec.name, app_spec.deployment_id)] = url

    def _handle_started(self, sender, app_spec):
        self._handle_signal(u"deploy_started", app_spec)

    def _handle_success(self, sender, app_spec):
        self._handle_signal(u"deploy_end", app_spec)

    def _handle_failure(self, sender, app_spec):
        self._handle_signal(u"deploy_end", app_spec, status=u"failure")

    def _handle_signal(self, event_name, app_spec, status=u"success"):
        base_url = self._callback_urls.get((app_spec.name, app_spec.deployment_id))
        if not base_url:
            self._logger.info(
                "No base URL for {} (deployment_id={}) found, not posting to pipeline".format(app_spec.name, app_spec.deployment_id))
            return
        task_name = u"fiaas_{}-{}_{}".format(self._environment, self._infrastructure, event_name)
        url = posixpath.join(base_url, task_name, status)
        r = self._session.post(url, json={u"description": u"From fiaas-deploy-daemon"})
        self._logger.info("Posted {} for app {} (deployment_id={}) to pipeline, return code={}".format(
            status, app_spec.name, app_spec.deployment_id, r.status_code))
        self._empty_status_logs(app_spec)

    @staticmethod
    def _empty_status_logs(app_spec):
        """Clear the status logs from the collector

        Pipeline doesn't have a good place to dump the logs, so we just make sure to empty out the log-collector every
        time we handle a signal. Once this code is taken out of fiaas-deploy-daemon, this is no longer a problem.
        """
        get_final_logs(app_spec)
