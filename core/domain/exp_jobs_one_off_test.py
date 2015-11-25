# coding: utf-8
#
# Copyright 2014 The Oppia Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS-IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Jobs for explorations."""

__author__ = 'Frederik Creemers'

"""Tests for Exploration-related jobs."""

from core import jobs_registry
from core.domain import exp_domain
from core.domain import exp_jobs_one_off
from core.domain import exp_services
from core.domain import rights_manager
from core.platform import models
from core.tests import test_utils
import feconf
import utils
(job_models, exp_models,) = models.Registry.import_models([
   models.NAMES.job, models.NAMES.exploration])
search_services = models.Registry.import_search_services()


class ExpSummariesCreationOneOffJobTest(test_utils.GenericTestBase):
    """Tests for ExpSummary aggregations."""

    ONE_OFF_JOB_MANAGERS_FOR_TESTS = [
        exp_jobs_one_off.ExpSummariesCreationOneOffJob]

    def test_all_exps_publicized(self):
        """Test exploration summary batch job if all explorations are
        publicized.
        """

        # specify explorations that will be used in test
        exp_specs = [
            {'category': 'Category A',
             'title': 'Title 1'},
             {'category': 'Category B',
            'title': 'Title 2'},
            {'category': 'Category C',
             'title': 'Title 3'},
            {'category': 'Category A',
             'title': 'Title 4'},
            {'category': 'Category C',
             'title': 'Title 5'}
            ]

        self._run_batch_job_once_and_verify_output(
            exp_specs,
            default_status=rights_manager.ACTIVITY_STATUS_PUBLICIZED)

    def test_all_exps_public(self):
        """Test summary batch job if all explorations are public
        but not publicized."""

        exp_specs = [
            {'category': 'Category A',
             'title': 'Title 1'},
            {'category': 'Category B',
             'title': 'Title 2'},
            {'category': 'Category C',
             'title': 'Title 3'},
            {'category': 'Category A',
             'title': 'Title 4'},
            {'category': 'Category C',
             'title': 'Title 5'}]

        self._run_batch_job_once_and_verify_output(
            exp_specs,
            default_status=rights_manager.ACTIVITY_STATUS_PUBLIC)

    def test_exps_some_publicized(self):
        """Test summary batch job if some explorations are publicized."""

        exp_specs = [
            {'category': 'Category A',
             'status': rights_manager.ACTIVITY_STATUS_PUBLIC,
             'title': 'Title 1'},
            {'category': 'Category B',
             'status': rights_manager.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 2'},
            {'category': 'Category C',
             'status': rights_manager.ACTIVITY_STATUS_PRIVATE,
             'title': 'Title 3'},
            {'category': 'Category A',
             'status': rights_manager.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 4'},
            {'category': 'Category C',
             'status': rights_manager.ACTIVITY_STATUS_PUBLICIZED,
             'title': 'Title 5'}]

        self._run_batch_job_once_and_verify_output(exp_specs)

    def _run_batch_job_once_and_verify_output(
            self, exp_specs,
            default_title='A title',
            default_category='A category',
            default_status=rights_manager.ACTIVITY_STATUS_PUBLICIZED):
        """Run batch job for creating exploration summaries once and verify its
        output. exp_specs is a list of dicts with exploration specifications.
        Allowed keys are category, status, title. If a key is not specified,
        the default value is used.
        """
        with self.swap(
                jobs_registry, 'ONE_OFF_JOB_MANAGERS',
                self.ONE_OFF_JOB_MANAGERS_FOR_TESTS):

            # default specs
            default_specs = {'title': default_title,
                             'category': default_category,
                             'status': default_status}

            self.signup(self.ADMIN_EMAIL, self.ADMIN_USERNAME)
            self.login(self.ADMIN_EMAIL)
            self.ADMIN_ID = self.get_user_id_from_email(self.ADMIN_EMAIL)
            self.set_admins([self.ADMIN_EMAIL])

            # create and delete an exploration (to make sure job handles
            # deleted explorations correctly)
            exp_id = '100'
            self.save_new_valid_exploration(
                exp_id,
                self.ADMIN_ID,
                title=default_specs['title'],
                category=default_specs['category'])
            exploration = exp_services.get_exploration_by_id(exp_id)
            exp_services.delete_exploration(self.ADMIN_ID, exp_id)

            # get dummy explorations
            num_exps = len(exp_specs)
            expected_job_output = {}

            for ind in range(num_exps):
                exp_id = str(ind)
                spec = default_specs
                spec.update(exp_specs[ind])
                self.save_new_valid_exploration(
                    exp_id,
                    self.ADMIN_ID,
                    title=spec['title'],
                    category=spec['category'])
                exploration = exp_services.get_exploration_by_id(exp_id)

                # publish or publicize exploration
                if spec['status'] == rights_manager.ACTIVITY_STATUS_PUBLIC:
                    rights_manager.publish_exploration(self.ADMIN_ID, exp_id)
                elif (spec['status'] ==
                        rights_manager.ACTIVITY_STATUS_PUBLICIZED):
                    rights_manager.publish_exploration(self.ADMIN_ID, exp_id)
                    rights_manager.publicize_exploration(self.ADMIN_ID, exp_id)

                # do not include user_id here, so all explorations are not
                # editable for now (will be updated depending on user_id
                # in galleries)
                exp_rights_model = exp_models.ExplorationRightsModel.get(
                    exp_id)

                exploration = exp_services.get_exploration_by_id(exp_id)
                exploration_model_last_updated = exploration.last_updated
                exploration_model_created_on = exploration.created_on

                # manually create the expectated summary specifying title,
                # category, etc
                expected_job_output[exp_id] = exp_domain.ExplorationSummary(
                    exp_id,
                    spec['title'],
                    spec['category'],
                    exploration.objective,
                    exploration.language_code,
                    exploration.tags,
                    feconf.get_empty_ratings(),
                    spec['status'],
                    exp_rights_model.community_owned,
                    exp_rights_model.owner_ids,
                    exp_rights_model.editor_ids,
                    exp_rights_model.viewer_ids,
                    exp_rights_model.contributor_ids,
                    exploration.version,
                    exploration_model_created_on,
                    exploration_model_last_updated)

                # calling constructor for fields that are not required
                # and have no default value does not work b/c
                # unspecified fields will be empty list in
                # expected_job_output but will be unspecified in
                # actual_job_output
                if exploration.tags:
                    expected_job_output[exp_id].tags = exploration.tags
                if exp_rights_model.owner_ids:
                    expected_job_output[exp_id].owner_ids = (
                        exp_rights_model.owner_ids)
                if exp_rights_model.editor_ids:
                    expected_job_output[exp_id].editor_ids = (
                        exp_rights_model.editor_ids)
                if exp_rights_model.viewer_ids:
                    expected_job_output[exp_id].viewer_ids = (
                        exp_rights_model.viewer_ids)
                if exploration.version:
                    expected_job_output[exp_id].version = (
                        exploration.version)

            # run batch job
            job_id = (
                exp_jobs_one_off.ExpSummariesCreationOneOffJob.create_new())
            exp_jobs_one_off.ExpSummariesCreationOneOffJob.enqueue(job_id)
            self.process_and_flush_pending_tasks()

            # get job output
            actual_job_output = exp_services.get_all_exploration_summaries()

            # check job output
            self.assertEqual(actual_job_output.keys(),
                             expected_job_output.keys())

            # Note: 'exploration_model_last_updated' is not expected to be the
            # same, because it is now read from the version model representing
            # the exploration's history snapshot, and not the ExplorationModel.
            simple_props = ['id', 'title', 'category', 'objective',
                            'language_code', 'tags', 'ratings', 'status',
                            'community_owned', 'owner_ids',
                            'editor_ids', 'viewer_ids', 'version',
                            'exploration_model_created_on']
            for exp_id in actual_job_output:
                for prop in simple_props:
                    self.assertEqual(
                        getattr(actual_job_output[exp_id], prop),
                        getattr(expected_job_output[exp_id], prop))


class OneOffExplorationFirstPublishedJobTest(test_utils.GenericTestBase):

    EXP_ID = 'exp_id'

    def setUp(self):
        super(OneOffExplorationFirstPublishedJobTest, self).setUp()

    def test_first_published_time_of_exploration_that_is_unpublished(self):
        """This tests that, if an exploration is published, unpublished, and
        then published again, the job uses the first publication date as the
        first published datetime.
        """
        self.signup(self.ADMIN_EMAIL, self.ADMIN_USERNAME)
        self.login(self.ADMIN_EMAIL)
        self.admin_id = self.get_user_id_from_email(self.ADMIN_EMAIL)
        self.set_admins([self.ADMIN_EMAIL])

        self.signup(self.OWNER_EMAIL, self.OWNER_USERNAME)
        self.login(self.OWNER_EMAIL)
        self.owner_id = self.get_user_id_from_email(self.OWNER_EMAIL)

        exploration = self.save_new_valid_exploration(
            self.EXP_ID, self.owner_id, end_state_name='End')
        rights_manager.publish_exploration(self.owner_id, self.EXP_ID)
        job_id = exp_jobs_one_off.ExplorationFirstPublishedOneOffJob.create_new()
        exp_jobs_one_off.ExplorationFirstPublishedOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()
        exploration_rights = rights_manager.get_exploration_rights(self.EXP_ID)

        # Test to see whether first_published_msec was correctly updated.
        exp_first_published = exploration_rights.first_published_msec
        exp_rights_model = exp_models.ExplorationRightsModel.get(self.EXP_ID)
        last_updated_time_msec = utils.get_time_in_millisecs(
            exp_rights_model.last_updated)
        self.assertLess(
            exp_first_published, last_updated_time_msec)

        rights_manager.unpublish_exploration(self.admin_id, self.EXP_ID)
        rights_manager.publish_exploration(self.owner_id, self.EXP_ID)
        job_id = exp_jobs_one_off.ExplorationFirstPublishedOneOffJob.create_new()
        exp_jobs_one_off.ExplorationFirstPublishedOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        # Test to see whether first_published_msec remains the same despite the
        # republication.
        exploration_rights = rights_manager.get_exploration_rights(self.EXP_ID)
        self.assertEqual(
            exp_first_published, exploration_rights.first_published_msec)


class ExpSummariesContributorsOneOffJobTest(test_utils.GenericTestBase):

    ONE_OFF_JOB_MANAGERS_FOR_TESTS = [
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob]

    EXP_ID = 'exp_id'

    USERNAME_A = 'usernamea'
    USERNAME_B = 'usernameb'
    EMAIL_A = 'emaila@example.com'
    EMAIL_B = 'emailb@example.com'

    def setUp(self):
        super(ExpSummariesContributorsOneOffJobTest, self).setUp()

    def test_contributors_for_valid_contribution(self):
        """ Test that if only one committ is made, that the contributor
        list consists of that contributor's user id.
        """
        self.signup(self.EMAIL_A, self.USERNAME_A)
        self.login(self.EMAIL_A)
        self.user_a_id = self.get_user_id_from_email(self.EMAIL_A)

        exploration = self.save_new_valid_exploration(
            self.EXP_ID, self.user_a_id)
        job_id = exp_jobs_one_off.ExpSummariesContributorsOneOffJob.create_new()
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        exploration_summary = exp_services.compute_summary_of_exploration(exploration)
        self.assertEqual(
            [self.user_a_id], exploration_summary.contributor_ids)

    def test_repeat_contributors(self):
        """ Test that if the same user makes more than one commit that changes
        the content of an exploration, the user is only represented once in the
        list of contributors for that exploration.
        """
        self.signup(self.EMAIL_A, self.USERNAME_A)
        self.login(self.EMAIL_A)
        self.user_a_id = self.get_user_id_from_email(self.EMAIL_A)

        # have one user make two commits
        exploration = self.save_new_valid_exploration(
            self.EXP_ID, self.user_a_id, title='Original Title')
        exploration_model = exp_models.ExplorationModel.get(
            self.EXP_ID, strict=True, version=None)
        exploration_model.title = 'New title'
        exploration_model.commit(
            self.user_a_id, 'Changed title.', [])

        # Run the job to compute the contributor id's.
        job_id = exp_jobs_one_off.ExpSummariesContributorsOneOffJob.create_new()
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        # Verify that the length of the contributor list is one, and that
        # the list contains the user who made these commits.
        exploration_summary = exp_services.compute_summary_of_exploration(exploration)
        self.assertEqual(len(exploration_summary.contributor_ids), 1)
        self.assertEqual(
            [self.user_a_id], exploration_summary.contributor_ids)

    def test_contributors_with_only_reverts_not_counted(self):
        """ Test that contributors who have only done reverts do not
        have their user id appear in the contributor list.
        """
        # sign up two users
        self.signup(self.EMAIL_A, self.USERNAME_A)
        self.login(self.EMAIL_A)
        self.user_a_id = self.get_user_id_from_email(self.EMAIL_A)
        self.signup(self.EMAIL_B, self.USERNAME_B)
        self.user_b_id = self.get_user_id_from_email(self.EMAIL_B)
        # have one user make two commits
        exploration = self.save_new_valid_exploration(
            self.EXP_ID, self.user_a_id, title='Original Title')
        exploration_model = exp_models.ExplorationModel.get(
            self.EXP_ID, strict=True, version=None)
        exploration_model.title = 'New title'
        exploration_model.commit(
            self.user_a_id, 'Changed title.', [])

        # Have the second user revert version 2 to version 1
        exp_services.revert_exploration(self.user_b_id, self.EXP_ID, 2, 1)

        # Run the job to compute the contributor id's.
        job_id = exp_jobs_one_off.ExpSummariesContributorsOneOffJob.create_new()
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        # Verify that the committer list does not contain the user
        # who only reverted.
        exploration_summary = exp_services.compute_summary_of_exploration(exploration)
        self.assertNotIn(self.user_b_id, exploration_summary.contributor_ids)

    def test_nonhuman_committers_not_counted(self):
        # create a commit with the system user id
        exploration = self.save_new_valid_exploration(
            self.EXP_ID, feconf.SYSTEM_COMMITTER_ID, title='Original Title')
        # Run the job to compute the contributor id's.
        job_id = exp_jobs_one_off.ExpSummariesContributorsOneOffJob.create_new()
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()
        # check that the system id was not added to the exploration's
        # contributor id's
        exploration_summary = exp_services.compute_summary_of_exploration(exploration)
        self.assertNotIn(feconf.SYSTEM_COMMITTER_ID,
            exploration_summary.contributor_ids)

        # create a commit with the migration bot user id
        exploration_model = exp_models.ExplorationModel.get(
            self.EXP_ID, strict=True, version=None)
        exploration_model.title = 'New title'
        exploration_model.commit(
            feconf.MIGRATION_BOT_USERNAME, 'Changed title.', [])
        # Run the job to compute the contributor id's.
        job_id = exp_jobs_one_off.ExpSummariesContributorsOneOffJob.create_new()
        exp_jobs_one_off.ExpSummariesContributorsOneOffJob.enqueue(job_id)
        self.process_and_flush_pending_tasks()
        # check that the migration bot id was not added to the exploration's
        # contributor id's
        exploration_summary = exp_services.compute_summary_of_exploration(exploration)
        self.assertNotIn(feconf.MIGRATION_BOT_USERNAME,
            exploration_summary.contributor_ids)


class OneOffReindexExplorationsJobTest(test_utils.GenericTestBase):

    EXP_ID = 'exp_id'

    def setUp(self):
        super(OneOffReindexExplorationsJobTest, self).setUp()

        explorations = [exp_domain.Exploration.create_default_exploration(
            '%s%s' % (self.EXP_ID, i), 'title %d' % i, 'category%d' % i)
            for i in xrange(5)]

        for exp in explorations:
            exp_services.save_new_exploration('owner_id', exp)
            rights_manager.publish_exploration('owner_id', exp.id)

        self.process_and_flush_pending_tasks()

    def test_standard_operation(self):
        job_id = (exp_jobs_one_off.IndexAllExplorationsJobManager.create_new())
        exp_jobs_one_off.IndexAllExplorationsJobManager.enqueue(job_id)

        self.assertEqual(self.count_jobs_in_taskqueue(), 1)

        indexed_docs = []

        def add_docs_mock(docs, index):
            indexed_docs.extend(docs)
            self.assertEqual(index, exp_services.SEARCH_INDEX_EXPLORATIONS)

        add_docs_swap = self.swap(
            search_services, 'add_documents_to_index', add_docs_mock)

        with add_docs_swap:
            self.process_and_flush_pending_tasks()

        ids = [doc['id'] for doc in indexed_docs]
        titles = [doc['title'] for doc in indexed_docs]
        categories = [doc['category'] for doc in indexed_docs]

        for i in xrange(5):
            self.assertIn("%s%s" % (self.EXP_ID, i), ids)
            self.assertIn('title %d' % i, titles)
            self.assertIn('category%d' % i, categories)


class ExplorationMigrationJobTest(test_utils.GenericTestBase):

    ALBERT_EMAIL = 'albert@example.com'
    ALBERT_NAME = 'albert'

    VALID_EXP_ID = 'exp_id0'
    NEW_EXP_ID = 'exp_id1'
    EXP_TITLE = 'title'

    def setUp(self):
        super(ExplorationMigrationJobTest, self).setUp()

        # Setup user who will own the test explorations.
        self.ALBERT_ID = self.get_user_id_from_email(self.ALBERT_EMAIL)
        self.signup(self.ALBERT_EMAIL, self.ALBERT_NAME)

        self.process_and_flush_pending_tasks()

    def test_migration_job_does_not_convert_up_to_date_exp(self):
        """Tests that the exploration migration job does not convert an
        exploration that is already the latest states schema version.
        """
        # Create a new, default exploration that should not be affected by the
        # job.
        exploration = exp_domain.Exploration.create_default_exploration(
            self.VALID_EXP_ID, 'title', 'category')
        init_state = exploration.states[exploration.init_state_name]
        init_state.update_interaction_id('EndExploration')
        init_state.interaction.default_outcome = None
        exp_services.save_new_exploration(self.ALBERT_ID, exploration)
        self.assertEqual(
            exploration.states_schema_version,
            feconf.CURRENT_EXPLORATION_STATES_SCHEMA_VERSION)
        self._before_converted_yaml = exploration.to_yaml()

        # Start migration job on sample exploration.
        job_id = exp_jobs_one_off.ExplorationMigrationJobManager.create_new()
        exp_jobs_one_off.ExplorationMigrationJobManager.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        # Verify the exploration is exactly the same after migration.
        updated_exp = exp_services.get_exploration_by_id(self.VALID_EXP_ID)
        self.assertEqual(
            updated_exp.states_schema_version,
            feconf.CURRENT_EXPLORATION_STATES_SCHEMA_VERSION)
        after_converted_yaml = updated_exp.to_yaml()
        self.assertEqual(after_converted_yaml, self._before_converted_yaml)

    def test_migration_job_does_not_have_validation_fail_on_default_exp(self):
        """Tests that the exploration migration job does not have a validation
        failure for a default exploration (of states schema version 0), due to
        the exploration having a null interaction ID in its initial state.
        """
        self.save_new_exp_with_states_schema_v0(
            self.NEW_EXP_ID, self.ALBERT_ID, self.EXP_TITLE)

        # Start migration job on sample exploration.
        job_id = exp_jobs_one_off.ExplorationMigrationJobManager.create_new()
        exp_jobs_one_off.ExplorationMigrationJobManager.enqueue(job_id)
        self.process_and_flush_pending_tasks()

        # Verify the new exploration has been migrated by the job.
        updated_exp = exp_services.get_exploration_by_id(self.NEW_EXP_ID)
        self.assertEqual(
            updated_exp.states_schema_version,
            feconf.CURRENT_EXPLORATION_STATES_SCHEMA_VERSION)

        # Ensure the states structure within the exploration was changed.
        self.assertNotEqual(
            updated_exp.to_dict()['states'], self.VERSION_0_STATES_DICT)

    def test_migration_job_skips_deleted_explorations(self):
        """Tests that the exploration migration job skips deleted explorations
        and does not attempt to migrate.
        """
        self.save_new_exp_with_states_schema_v0(
            self.NEW_EXP_ID, self.ALBERT_ID, self.EXP_TITLE)

        # Note: This creates a summary based on the upgraded model (which is
        # fine). A summary is needed to delete the exploration.
        exp_services.create_exploration_summary(self.NEW_EXP_ID)

        # Delete the exploration before migration occurs.
        exp_services.delete_exploration(self.ALBERT_ID, self.NEW_EXP_ID)

        # Ensure the exploration is deleted.
        with self.assertRaisesRegexp(Exception, 'Entity .* not found'):
            exp_services.get_exploration_by_id(self.NEW_EXP_ID)

        # Start migration job on sample exploration.
        job_id = exp_jobs_one_off.ExplorationMigrationJobManager.create_new()
        exp_jobs_one_off.ExplorationMigrationJobManager.enqueue(job_id)

        # This running without errors indicates the deleted exploration is
        # being ignored, since otherwise exp_services.get_exploration_by_id
        # (used within the job) will raise an error.
        self.process_and_flush_pending_tasks()

        # Ensure the exploration is still deleted.
        with self.assertRaisesRegexp(Exception, 'Entity .* not found'):
            exp_services.get_exploration_by_id(self.NEW_EXP_ID)
