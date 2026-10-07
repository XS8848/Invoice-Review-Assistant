# -*- coding: utf-8 -*-
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from util import (  # noqa: E402
    TEST_PASSWORD,
    admin_token,
    auth,
    client,
    employee,
    new_emp_no,
    register_employee,
    upload_files,
    wait_terminal,
)
