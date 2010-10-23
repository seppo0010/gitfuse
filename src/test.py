import unittest
import os
from git import *

class TestGitFuse(unittest.TestCase):
	path = None
	repoPath = None
	repo = None

	def setUp(self):
		self.repoPath = os.getenv('GITPYTHON_TEST_REPO_DIR').rstrip('/') + '/';
		self.path = os.getenv('GITPYTHON_TEST_DIR').rstrip('/') + '/';
		self.repo = Repo(self.repoPath)

	def test_create_empty_file(self):
		fp = open(self.path + 'asd', 'w', 0755)
		fp.close()
		repo = Repo(self.repoPath)
		stats = repo.head.commit.parents[0].stats # HEAD is the file edit - parent is the first commit creating the file
		self.assertEqual(stats.total['files'], 1)

	def test_edit_file(self):
		fp = open(self.path + 'asd', 'w', 0755)
		fp.write('hello\nworld')
		fp.close()
		stats = self.repo.head.commit.stats
		self.assertEqual(stats.files['asd']['insertions'], 2)


	def test_delete_file(self):
		os.unlink(self.path + 'asd')
		diffIndex = self.repo.head.commit.parents[0].diff(self.repo.head.commit)
		runDeleted = False
		for diff in diffIndex.iter_change_type('D'):
			runDeleted = True
			self.assertEqual(diff.a_blob.path, 'asd')
			self.assertEqual(diff.deleted_file, True)
		self.assertEqual(runDeleted, True)


if __name__ == '__main__':
    unittest.main()
