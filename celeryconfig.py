from core.config import config


BROKER_HOST = config.get('rabbitmq', 'host')

BROKER_PORT = 5672
BROKER_USER = "bermuda"
BROKER_PASSWORD = "bermuda"

BROKER_VHOST = "/"

BROKER_URL = 'amqp://{0}:{1}@{2}:{3}//'.format(BROKER_USER, BROKER_PASSWORD, BROKER_HOST, BROKER_PORT)

#CELERY_RESULT_BACKEND = "amqp"
#CELERY_TASK_RESULT_EXPIRES = 3600

CELERY_IMPORTS = ("core.splitter","core.splitter_new","core.splitter_refreshDevice","core.url_refresh","core.dir_refresh","core.preload_worker","core.preload_worker_new","core.cert_trans_worker","core.cert_query_worker","core.transfer_cert_worker",
				  "receiver.retry_task","core.rcms_change_worker","core.async_device_result",
				  "receiver.receiver_branch", "core.link_detection_all", 'util.preload_url_timer_task_commit',
				  "core.splitter_autodesk", "core.autodesk_url_id", "core.preload_webluker","core.physical_refresh")

CELERY_ROUTES = { "core.url_refresh.work": {"queue": "refresh"},
	                "core.dir_refresh.work": {"queue": "refresh"},
	                "core.preload_worker.dispatch": {"queue": "preload"},
	                "core.preload_worker_new.dispatch": {"queue": "preload"},
	                "core.preload_worker.preload_cancel": {"queue": "preload"},
	                "core.preload_worker.execute_retry_task": {"queue": "preload"},
	                # "core.preload_worker.execute_hangup_task": {"queue": "preload"},
	                "core.preload_worker.save_fc_report": {"queue": "preload"},
	                "core.preload_worker_new.save_fc_report": {"queue": "preload"},
				    "core.async_device_result.async_devices":{"queue":"async_devices"},
				    # "core.link_detection.link_detection":{"queue":"subcenter"},
				    "core.link_detection_all.link_detection_refresh": {"queue": "subcenter"},
                    "receiver.retry_task.retry_worker":{"queue":"retry_task"},
                    "receiver.retry_task.retry_new_worker":{"queue":"retry_task"},
                    "core.rcms_change_worker.get_new_info":{"queue":"rcms_change"},
	                "core.preload_worker.reset_error_tasks": {"queue": "preload"},
	                "core.preload_worker_new.reset_error_tasks": {"queue": "preload"},
				    "receiver.receiver_branch.update_refresh_result":{"queue": "refresh_report"},
				    "core.link_detection_all.link_detection_preload": {"queue": "subcenter_preload"},
				    "core.link_detection_all.link_detection_cert": {"queue": "subcenter_cert"},
				    #"core.autodesk_url_id.udpate_url_dev_autodesk": {"queue": "autodesk_url_id"},
				    "util.preload_url_timer_task_commit.commit_preload_timer_task": {"queue": "preload_timer"},
					"core.autodesk_url_id.update_url_autodesk": {"queue": "autodesk_url_id"},
				    # "core.autodesk_url_id.udpate_url_dev_autodesk": {"queue": "autodesk_url_id"},
				    "core.autodesk_url_id.failed_task_email": {"queue": "autodesk_failed_email"},
				    "core.autodesk_url_id.failed_task_email_other": {"queue": "autodesk_failed_email_other"},
                                    "core.cert_trans_worker.dispatch": {"queue": "cert_worker"},
                                    "core.cert_trans_worker.save_result": {"queue": "cert_report"},
                                    "core.cert_trans_worker.check_cert_task": {"queue": "cert_check"},
                                    "core.cert_query_worker.dispatch": {"queue": "cert_query_worker"},
                                    "core.cert_query_worker.check_cert_query_task": {"queue": "cert_query_check"},
                                    "core.cert_query_worker.save_result": {"queue": "cert_query_report"},
                                    "core.transfer_cert_worker.dispatch": {"queue": "transfer_cert_worker"},
                                    "core.transfer_cert_worker.check_transfer_cert_task": {"queue": "transfer_cert_check"},
                                    "core.transfer_cert_worker.save_result": {"queue": "transfer_cert_report"},
				     # refresh_last_hpcc_report
				    "core.autodesk_url_id.refresh_last_hpcc_report": {"queue": "refresh_last_result_report_email"},
				    "core.preload_webluker.task_forward": {"queue": "preload_webluker"},
				    "core.physical_refresh.work":{"queue":"url_physical"}

				    }

CELERY_ACKS_LATE = True
CELERYD_HIJACK_ROOT_LOGGER = False
CELERY_SEND_EVENTS = True
