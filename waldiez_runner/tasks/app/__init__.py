# SPDX-License-Identifier: Apache-2.0.
# Copyright (c) 2024 - 2025 Waldiez and contributors.
"""The app to run when a new task is created."""

# this whole folder is meant to be copied to the task's folder
# in a new virtualenv with the relevant dependencies
# (waldiez and faststream)
# and be called from the taskiq's runner
# we need the `task_id`, `redis_url` arguments
# and the `.waldiez` file to be present in the task's folder
