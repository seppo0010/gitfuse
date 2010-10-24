import unittest
import os
import stat
import time
from git import *

class TestGitFuse(unittest.TestCase):
	path = None
	repoPath = None
	repo = None

	def setUp(self):
		self.repoPath = os.getenv('GITPYTHON_TEST_REPO_DIR').rstrip('/') + '/';
		self.path = os.getenv('GITPYTHON_TEST_DIR').rstrip('/') + '/';
		self.repo = Repo(self.repoPath)

        def test_change_file_permissions(self):
		testtext = 'This is a sample text to write on the file'

                fp = open(self.path + 'permissions', 'w')
		fp.write(testtext)
                fp.close()
		os.chmod(self.path + 'permissions', 0755)
		statinfo = os.stat(self.path + 'permissions')
		self.assertTrue(statinfo.st_mode & 0755 == 0755) # There are other flags besides permissions
		self.assertEqual(statinfo.st_mode & stat.S_IFDIR, 0)
		self.assertEqual(statinfo.st_mode & stat.S_IFREG, stat.S_IFREG)
		self.assertEqual(statinfo.st_size, len(testtext))
		self.assertTrue(time.time() - statinfo.st_atime < 2)
		self.assertTrue(time.time() - statinfo.st_mtime < 2)
		self.assertTrue(time.time() - statinfo.st_ctime < 2)

		#NOTE: we are checking local permissions, not git permissions.
		#This is related to git design limitations and cross platform support.

	def test_create_empty_file(self):
		fp = open(self.path + 'data', 'w')
		fp.close()
		repo = Repo(self.repoPath)
		stats = repo.head.commit.parents[0].stats # HEAD is the file edit - parent is the first commit creating the file
		self.assertEqual(stats.total['files'], 1)

	def test_edit_file(self):
		fp = open(self.path + 'data', 'w')
		fp.write('hello\nworld')
		fp.close()
		stats = self.repo.head.commit.stats
		self.assertEqual(stats.files['data']['insertions'], 2)


	def test_delete_file(self):
		os.unlink(self.path + 'data')
		diffIndex = self.repo.head.commit.parents[0].diff(self.repo.head.commit)
		runDeleted = False
		for diff in diffIndex.iter_change_type('D'):
			runDeleted = True
			self.assertEqual(diff.a_blob.path, 'data')
			self.assertEqual(diff.deleted_file, True)
		self.assertEqual(runDeleted, True)


if __name__ == '__main__':
	suite = unittest.TestLoader().loadTestsFromTestCase(TestGitFuse)
	unittest.TextTestRunner(verbosity=2).run(suite)
