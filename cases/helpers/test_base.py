import logging
from subprocess import check_output, CalledProcessError
from selenium import webdriver
from pages.login_page import LoginPage
from fabric.api import settings, run, get, put


log = logging.getLogger('bender')


class CheckBase(object):
    """"""

    def __init__(self):
        self._host_string = None
        self._host_user = None
        self._host_pass = None
        self._browser = None
        self._build = None
        self._cases = None
        self._config = None
        self._driver = None

    @property
    def host_string(self):
        return self._host_string

    @host_string.setter
    def host_string(self, val):
        self._host_string = val

    @property
    def host_user(self):
        return self._host_user

    @host_user.setter
    def host_user(self, val):
        self._host_user = val

    @property
    def host_pass(self):
        return self._host_pass

    @host_pass.setter
    def host_pass(self, val):
        self._host_pass = val

    @property
    def browser(self):
        return self._browser

    @browser.setter
    def browser(self, val):
        self._browser = val

    @property
    def build(self):
        return self._build

    @build.setter
    def build(self, val):
        self._build = val

    @property
    def cases(self):
        return self._cases

    @cases.setter
    def cases(self, val):
        self._cases = val

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, val):
        self._config = val

    def get_remote_file(self, remote_path, local_path):
        with settings(
                host_string=self.host_string,
                user=self.host_user,
                password=self.host_pass,
                disable_known_hosts=True,
                connection_attempts=120):
            ret = get(remote_path, local_path)
            if not ret.succeeded:
                raise ValueError("Can't get {} from remote server:{}.".format(
                    remote_path, self.host_string))

    def put_remote_file(self, local_path, remote_path):
        with settings(
                host_string=self.host_string,
                user=self.host_user,
                password=self.host_pass,
                disable_known_hosts=True,
                connection_attempts=120):
            ret = put(local_path, remote_path)
            if not ret.succeeded:
                raise ValueError("Can't put {} to remote server:{}.".format(
                    local_path, self.host_string))

    def run_cmd(self, cmd, timeout=60):
        ret = None
        try:
            with settings(
                    host_string=self.host_string,
                    user=self.host_user,
                    password=self.host_pass,
                    disable_known_hosts=True,
                    connection_attempts=60):
                ret = run(cmd, quiet=True, timeout=timeout)
                if ret.succeeded:
                    log.info('Run cmd "%s" succeeded\n"%s"', cmd, ret)
                    return True, ret
                else:
                    log.error('Run cmd "%s" failed\n"%s"', cmd, ret)
                    return False, ret
        except Exception as e:
            log.error('Run cmd "%s" failed with exception "%s"', cmd, e)
            return False, e

    def local_cmd(self, cmd):
        try:
            ret = check_output(cmd, shell=True)
        except CalledProcessError as e:
            log.error('Local cmd "%s" failed\n"%s"', cmd, e.output)
            return False, e.output
        else:
            return True, ret

    def call_func_by_name(self, name=''):
        func = getattr(self, name.lower(), None)
        if func:
            return func()
        else:
            raise NameError(
                'The checkpoint function {} is not defined'.format(name))

    def run_checkpoint(self, checkpoint, cases, cks):
        try:
            log.info("Start to run checkpoint:%s for cases:%s", checkpoint, cases)
            ck = self.call_func_by_name(checkpoint)
            if ck:
                newck = 'passed'
            else:
                newck = 'failed'
            for case in cases:
                cks[case] = newck
        except Exception as e:
            log.exception(e)
        finally:
            log.info("Run checkpoint:%s for cases:%s finished.", checkpoint, cases)

    def _get_checkpoint_cases_map(self):
        id_ckp_map = self._cases  # {$polarion_id: $checkpoint}

        from collections import OrderedDict
        checkpoint_cases_map = OrderedDict()

        if not id_ckp_map:
            return checkpoint_cases_map

        for id, ckp in id_ckp_map.items():
            if ckp in checkpoint_cases_map:
                checkpoint_cases_map[ckp].append(id)
            else:
                checkpoint_cases_map[ckp] = []
                checkpoint_cases_map[ckp].append(id)

        return checkpoint_cases_map
 
    def run_cases(self):
        cks = {}
        # get checkpoint cases map
        checkpoint_cases_map = self._get_checkpoint_cases_map()

        # run check
        log.info("Start to run check points, please wait...")

        for checkpoint, cases in checkpoint_cases_map.items():
            self.run_checkpoint(checkpoint, cases, cks)

        return cks

    def init_browser(self):
        if self.browser == 'firefox':
            driver = webdriver.Firefox()
            driver.implicitly_wait(20)
            driver.root_uri = "https://{}:9090".format(self.host_string)
        elif self.browser == 'chrome':
            driver = webdriver.Chrome()
            driver.implicitly_wait(20)
            driver.root_uri = "https://{}:9090".format(self.host_string)
        else:
            raise NotImplementedError
        driver.maximize_window()
        self._driver = driver

    def cockpit_login(self):
        login_page = LoginPage(self._driver)
        login_page.basic_check_elements_exists()
        login_page.login_with_credential(self.host_user, self.host_pass)

    def set_page(self):
        pass

    def close_browser(self):
        if self._driver:
            self._driver.close()

    def setup(self):
        log.info("Setup work before testing...")
        log.info("Init browser")
        self.init_browser()
        log.info("Login cockpit")
        self.cockpit_login()
        log.info("Init page")
        self.set_page()

    def teardown(self):
        log.info("Teardown work after testing...")
        self.close_browser()
        log.info("Closed the browser")

    def go_check(self):
        cks = {}
        try:
            self.setup()
            cks = self.run_cases()
        except Exception as e:
            log.exception(e)
        finally:
            self.teardown()

        return cks


def paged(page_cls):
    def decorator(func):
        def wrapper(self, *args, **ks):
            self.set_page(page_cls)
            return func(*args, **ks)
        return wrapper
    return decorator
