from celery import Celery, Task
from flask import Flask
from config import Config

def celery_init_app(app: Flask) -> Celery:
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    celery_app = Celery(app.name, broker=Config.celeryBrokerUrl, task_cls=FlaskTask)
    celery_app.conf.update({"CELERY_RESULT_BACKEND": Config.celeryResultBackend})
    celery_app.set_default()
    app.extensions["celery"] = celery_app
    return celery_app

