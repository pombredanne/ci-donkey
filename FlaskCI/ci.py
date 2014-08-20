from datetime import datetime as dtdt
from . import app
import subprocess
import shlex
import git
import uuid
import os
import json
import re
import thread
import traceback
import shutil
import time
import tempfile

def dt_from_str(dstr):
    return dtdt.strptime(dstr, app.config['DATETIME_FORMAT'])

def setup_cls():
    if os.path.exists(app.config['SETUP_FILE']):
        obj = json.load(open(app.config['SETUP_FILE'], 'r'))
        obj['datetime'] = dt_from_str(obj['datetime'])
        return type('CISetup', (), obj)

def build():
    b = Build()
    thread.start_new_thread(b.build, ())
    return b.uuid

def _now():
    return dtdt.utcnow().strftime(app.config['DATETIME_FORMAT'])

def _build_log_path(id):
    return os.path.join('/tmp', id + '.log')

class KnownError(Exception):
    pass

class CommandError(Exception):
    pass

TERMINAL_ERROR =   '#############   TERMINAL ERROR   #############\n'
TEST_ERROR =       '#############     TEST ERROR     #############\n'
LOG_PRE_FINISHED = '############# PRE BUILD FINISHED #############\n'
LOG_FINISHED =     '#############      FINISHED      #############\n'


class Build(object):
    def __init__(self, delete_after = True):
        self.setup = setup_cls()
        self.uuid = str(uuid.uuid4())
        self.delete_after = delete_after
        self.log_file = _build_log_path(self.uuid)
        self._log('Starting build at %s' % _now())
        self._log('log filename: %s' % self.log_file)
        self.tmp_path = os.path.join(tempfile.gettempdir(), self.uuid)
        self._log('project directory: %s' % self.tmp_path)
        self.pre_script = []
        self.main_script = []

    @staticmethod
    def log_info(build_id, pre_script = None, main_script = None):
        if pre_script == None and main_script == None:
            script_path = Build._build_script_path(build_id)
            if os.path.exists(script_path):
                pre_script, main_script = json.load(open(script_path, 'r'))
        with open(_build_log_path(build_id), 'r') as logfile:
            log = logfile.read()
            m = re.search('Starting build at (.*)', log)
            datetime = m.groups()[0]
            prelog = log
            mainlog = None
            prefin = LOG_PRE_FINISHED in log
            if prefin:
                prelog, mainlog = prelog.split(LOG_PRE_FINISHED)
                prelog += LOG_PRE_FINISHED
            term_error = TERMINAL_ERROR in log
            finished = LOG_FINISHED in log or term_error
            test_passed = TEST_ERROR not in log and finished and not term_error
            local = locals()
            status = {name: local[name] for name in 
            ['build_id', 'datetime', 'prelog', 'mainlog', 'prefin', 'term_error', 
            'finished', 'test_passed', 'pre_script', 'main_script']}
            return status

    @staticmethod
    def history():
        logs = []
        if os.path.exists(app.config['LOG_FILE']):
            logs = json.load(open(app.config['LOG_FILE'], 'r'))
        return logs

    def set_url(self):
        self.url = self.setup.git_url
        t = self.setup.github_token
        if len(t) > 0:
            self.url = re.sub('https://', 
                'https://%s@' % t, self.url)
            self._log('clone url: %s' % self.url.replace(t, '<token>'))
        else:
            self._log('clone url: %s' % self.url)

    def build(self):
        try:
            if not self.prebuild(): return
            if not self.main_build(): return
        except Exception, e:
            raise e
        finally:
            self._finish()

    def prebuild(self):
        try:
            # first we save a blank log item so it's in history
            logs = Build.history()
            logs.append(Build.log_info(self.uuid))
            self._save_logs(logs)

            self.set_url()
            self._set_svg('in_progress')
            self.download()
            self.get_ci_script()
            self.execute(self.pre_script)
        except Exception, e:
            self._error(e)
            return False
        else:
            self._message(LOG_PRE_FINISHED)
            return True

    def download(self):
        self._log('cloning...')
        git.Git().clone(self.url, self.tmp_path)
        self._log('cloned code successfully')

    def get_ci_script(self):
        ci_script_name = self.setup.ci_script
        ci_script_path = os.path.join(self.tmp_path, ci_script_name)
        if not os.path.exists(ci_script_path):
            raise KnownError('Repo has no CI script file: %s' % ci_script_name)
        ci_script = open(ci_script_path, 'r').read()
        self._log('found CI script: %s' % ci_script_name)
        if self.setup.main_tag not in ci_script:
            raise KnownError('Config has no divider: %s' % self.setup.main_tag)
        current_script = []
        for line in ci_script.split('\n'):
            if self.setup.pre_tag in line or line == '':
                current_script = self.pre_script
                continue
            if self.setup.main_tag in line:
                current_script = self.main_script
                continue
            current_script.append(line)
        obj = (self.pre_script, self.main_script)
        json.dump(obj, open(Build._build_script_path(self.uuid), 'w'), indent = 2)

    @staticmethod
    def _build_script_path(id):
        return os.path.join('/tmp', id + '.script')

    def main_build(self):
        try:
            self.execute(self.main_script)
        except Exception, e:
            self._error(e, True)
            return False
        else:
            self._message(LOG_FINISHED)
            return True

    def execute(self, commands):
        for command in commands:
            if command.strip().startswith('#'):
                self._log(command, 'SKIP> ')
                continue
            self._log(command, 'EXEC> ')
            cargs = shlex.split(command)
            try:
                p = subprocess.Popen(cargs, 
                    cwd = self.tmp_path, 
                    stdout = subprocess.PIPE,
                    stderr = subprocess.PIPE)
                stdout, stderr = p.communicate()
                self._log(stdout, '')
                if p.returncode != 0:
                    raise CommandError(stderr)
            except CommandError, e:
                raise e
            except Exception, e:
                raise KnownError('%s: %s' % (e.__class__.__name__, str(e)))

    def _error(self, e, errors_expected = False):
        if errors_expected and isinstance(e, CommandError):
            self._log('%s: %s' % (e.__class__.__name__, str(e)), '')
            self._message(TEST_ERROR)
            self._message(LOG_FINISHED)
            return
        if isinstance(e, KnownError) or isinstance(e, CommandError):
            self._log('%s: %s' % (e.__class__.__name__, str(e)), '')
        else:
            tb = traceback.format_exc()
            self._log(tb)
        self._message(TERMINAL_ERROR)

    def _finish(self):
        # make sure log file has finished being written
        self._log('Build finished at %s, cleaning up...' % _now())
        time.sleep(2)
        if self.delete_after and os.path.exists(self.tmp_path):
            shutil.rmtree(self.tmp_path, ignore_errors = False)
        logs = [log for log in Build.history() if log['build_id'] != self.uuid]
        log_info = Build.log_info(self.uuid, self.pre_script, self.main_script)
        logs.append(log_info)
        self._set_svg(log_info['test_passed'])
        self._save_logs(logs)
        if self.delete_after:
            os.remove(self.log_file)
            os.remove(Build._build_script_path(self.uuid))

    def _set_svg(self, status):
        if status == 'in_progress':
            filename = 'in_progress.svg'
        else:
            filename = 'passing.svg' if status else 'failing.svg'
        thisdir = os.path.dirname(__file__)
        src = os.path.join(thisdir, 'static', filename)
        shutil.copyfile(src, app.config['STATUS_SVG_FILE'])

    def _save_logs(self, logs):
        json.dump(logs, open(app.config['LOG_FILE'], 'w'), indent = 2)

    def _message(self, message):
        with open(self.log_file, 'a') as logfile:
            logfile.write(message)
            logfile.flush()

    def _log(self, line, prefix = '#> '):
        # print line
        with open(self.log_file, 'a') as logfile:
            logfile.write(prefix + line.strip('\n \t') + '\n')
            logfile.flush()