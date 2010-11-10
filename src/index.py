#!/usr/bin/env python
# -*- coding: utf-8 -*-
import errno
import fuse
import stat
import time
import os
import sys
import ConfigParser
import getopt
from git import *
from multiprocessing import Process
import hooks

fuse.fuse_python_api = (0, 2)



def shellquote(s):
	return "\"" + s.replace("\"", "\\\"") + "\""

class GitFuse(fuse.Fuse):
	basePath = ""
	openFiles = {}
	remote = None
	syncFreq = 60 # in seconds
	remoteNotification = None
	verbose = False
	hooks = []

	def __init__(self, *args, **kw):
		opts, args = getopt.getopt(sys.argv[2:], "v", ['mountunit='])
		mountunit = None
		self.verbose = False
		for o, a in opts:
			if o == "-v":
				self.verbose = True
			elif o == "--mountunit":
				mountunit = a

		config = ConfigParser.ConfigParser()
		config.read([os.path.expanduser('~/.gitfuserc')])

		try:
			if mountunit == None:
				mountunit = config.get('default', 'repository')
		except ConfigParser.NoOptionError:
			sys.exit('Mountunit is required. You can set it as parameter, or in ~/.gitfuserc as repository in default section.')

		self.argv = sys.argv
		sys.argv = [self.argv[0], self.argv[1]]
		fuse.Fuse.__init__(self, *args, **kw)

		try:
			self.basePath = config.get(mountunit, 'path');
			self.basePath = os.path.expanduser(self.basePath.rstrip('/')) + '/'
		except ConfigParser.Error:
			sys.exit('Unable to find repository path');

		self.repo = Repo(self.basePath)
		assert self.repo.bare == False

		for attr in hooks.__all__:
			fnc = hooks.__getattribute__(attr)
			self.hooks.append(fnc(self))

		if config.has_option(mountunit, 'remote'):
			if config.has_option(mountunit, 'remote-frequency'):
				self.syncFreq = config.getint(mountunit, 'remote-frequency')
			if config.has_option(mountunit, 'remote-notification'):
				self.remoteNotification = config.get(mountunit, 'remote-notification')
			self.remote = config.get(mountunit, 'remote')
			self.syncTimer = Process(None, self.gitsync)
			self.syncTimer.start()

	def getattr(self, path):
		self.debug(str(['getattr', path]))
		for hook in self.hooks:
			if hasattr(hook, "respond_getattr") and callable(getattr(hook, "respond_getattr")) and hook.respond_getattr(path):
				return hook.getattr(path)
		realpath = self.getpath(path)
		ret = os.lstat(realpath)
		self.debug(str(['return', 'getattr', path, str(ret)]))
		return ret

	def mknod(self, path, mode, dev):
		self.debug(str(['mknod', path, mode, dev]))
		realpath = self.getpath(path)
		fp = open(realpath, 'w')
		fp.close()
		index = self.repo.index
		index.add([realpath])
		index.commit('Created file')
		self.debug(str(['return', 'mknod', path, mode, dev]))
		return 0

	def open(self, path, flags):
		self.debug(str(['open', path, flags]))
		openmode = self.getmodeforflag(flags)
		if (path in self.openFiles and openmode in self.openFiles[path]):
			self.openFiles[path][openmode]["count"] += 1
			return 0

		fp = open(self.getpath(path), openmode)
		if (path not in self.openFiles):
			self.openFiles[path] = {}
		self.openFiles[path][openmode] = {"fp":fp,"count":1}
		self.debug(str(['return', 'open', path, flags]))
		return 0

	def read(self, path, size, offset):
		self.debug(str(['read', path, size, offset]))
		self.open(path, 0)
		fp = self.openFiles[path]['r+']["fp"]
		fp.seek(offset, os.SEEK_SET)
		ret = fp.read(size)
		self.debug(str(['return', 'read', path, size, offset, str(ret)]))
		self.release(path, 0)
		return ret

	def release(self, path, flags):
		self.debug(str(['release', path, flags]))
		openmode = self.getmodeforflag(flags)
		if (path in self.openFiles and openmode in self.openFiles[path]):
			self.openFiles[path][openmode]["count"] -= 1
			if (self.openFiles[path][openmode]["count"] == 0):
				self.openFiles[path][openmode]["fp"].close()
				if (openmode == 'a+'):
					index = self.repo.index
					index.add([self.getpath(path)])
					index.commit('Edited file')
				del self.openFiles[path][openmode]
		self.debug(str(['return', 'release', path, flags]))
		return

	def write(self, path, buf, offset):
		self.debug(str(['write', path, buf, offset]))
		self.open(path, 1)
		fp = self.openFiles[path]['a+']["fp"]

		fp.truncate(offset)
		fp.write(str(buf))
		fp.flush()
		os.fsync(fp.fileno())
		ret = len(buf)
		self.release(path, 1)
		self.debug(str(['return', 'write', path, buf, offset, ret]))
		return ret

	def truncate(self, path, size):
		self.debug(str(['truncate', path, size]))
		self.open(path, 1)
		fp = self.openFiles[path]['a+']["fp"]
		ret = fp.truncate(size)
		self.release(path, 1)
		self.debug(str(['return', 'truncate', path, size, ret]))
		return ret

	def utime(self, path, times):
		self.debug(str(['utime', path, times]))
		ret = os.utime(self.getpath(path), times)
		self.debug(str(['return', 'utime', path, times, ret]))
		return ret

	def mkdir(self, path, mode):
		self.debug(str(['mkdir', path, mode]))
		ret = os.mkdir(self.getpath(path), mode)
		self.debug(str(['return', 'mkdir', path, mode, ret]))
		return ret

	def rmdir(self, path):
		self.debug(str(['rmdir', path]))
		ret = os.rmdir(self.getpath(path))
		self.debug(str(['return', 'rmdir', path, ret]))
		return ret

	def rename(self, pathfrom, pathto):
		self.debug(str(['rename', pathfrom, pathto]))
		src = self.getpath(pathfrom)
		target = self.getpath(pathto)
		ret = os.rename(src, target)
		if os.path.isdir(target) == False or os.listdir(target) != []:
			index = self.repo.index
			index.add([target])
			index.remove([src], r="")
			index.commit('Renamed folder/file')
		self.debug(str(['return', 'rename', pathfrom, pathto, ret]))
		return ret

	def fsync(self, path, isfsyncfile):
		self.debug(str(['fsync', path, isfsyncfile]))
		self.open(path, 1)
		fp = self.openFiles[path]['a+']["fp"]
		ret = os.fsync(fp)
		self.debug(str(['return', 'fsync', path, isfsyncfile, ret]))
		self.release(path, 1)
		return ret

	def readdir(self, path, offset):
		self.debug(str(['readdir', path, offset]))
		for e in '.', '..':
			yield fuse.Direntry(e);

		if path == '/':
			yield fuse.Direntry('.gitfuserepo');

		for e in os.listdir(self.basePath + path):
			if (path != '/' or e != '.git'):
				yield fuse.Direntry(e);
		self.debug(str(['return', 'readdir', path, offset]))

	def chmod(self, path, mode):
		self.debug(str(['chmod', path, mode]))
		realpath = self.getpath(path)
		ret = os.chmod(realpath, mode)
		index = self.repo.index
		index.add([realpath])
		index.commit('Changed file permissions')
		self.debug(str(['return', 'chmod', path, mode, ret]))
		return ret

	def unlink(self, path):
		self.debug(str(['unlink', path]))
		realpath = self.getpath(path)
		ret = os.unlink(realpath)
		index = self.repo.index
		index.remove([realpath])
		index.commit('Deleted file')
		self.debug(str(['return', 'unlink', path, ret]))
		return ret

	def chown(self, path, uid, gid):
		self.debug(str(['chown', path, uid, gid]))
		realpath = self.getpath(path)
		ret = os.chown(realpath, uid, gid)
		self.debug(str(['return', 'chown', path, uid, gid, ret]))
		return ret

	def statfs(self):
		self.debug(str(['statfs']))
		ret = os.statvfs(self.basePath);
		self.debug(str(['return', 'statfs', ret]))
		return ret

	def link(self, targetPath, linkPath):
		self.debug(str(['link', targetPath, linkPath]))
		return -errno.ENOSYS

	def readlink(self, path):
		self.debug(str(['readlink', path]))
		for hook in self.hooks:
			if hasattr(hook, "respond_readlink") and callable(getattr(hook, "respond_readlink")) and hook.respond_readlink(path):
				return hook.readlink(path)

		realpath = self.getpath(path)
		ret = os.readlink(realpath)
		self.debug(str(['return', 'readlink', path, ret]))
		return ret

	def symlink(self, targetPath, linkPath):
		self.debug(str(['symlink', targetPath, linkPath]))
		target = self.getpath(targetPath)
		link = self.getpath(linkPath)
		ret = os.symlink(target, link)
		index = self.repo.index
		index.add([realpath])
		index.commit('Created symlink')
		self.debug(str(['return', 'symlink', targetPath, linkPath, ret]))
		return ret

	def getmodeforflag(self, flag):
		if flag & 1 > 0:
			return 'a+'
		else:
			return 'r+'

	def getpath(self, path):
		return self.basePath + path.lstrip('/');

	def debug(self, text):
		return
		f = open('/tmp/workfile', 'a+')
		f.write(text)
		f.write("\n")
		f.close()

	def gitsync(self):
		try:
			remote = self.repo.remotes[self.remote]
			while True:
				time.sleep(self.syncFreq)
				fetch = remote.fetch()
				if self.remoteNotification != None:
					for info in fetch:
						if self.repo.head.commit == info.commit:
							continue
						diffIndex = info.commit.diff(self.repo.head.commit)
						notification_str = 'Changes by ' + str(info.commit.committer) + "\n"
						for diff_added in diffIndex.iter_change_type('A'):
							notification_str += 'Added ' + str(diff_added.b_blob.path) + "\n"
						for diff_deleted in diffIndex.iter_change_type('D'):
							notification_str += 'Deleted ' + str(diff_deleted.a_blob.path) + "\n"
						for diff_renamed in diffIndex.iter_change_type('R'):
							pass
							#print 'Renamed ' + str(diff_renamed.a_blob.path)
							#print 'Renamed ' + str(diff_renamed.b_blob.path)
						for diff_modified in diffIndex.iter_change_type('M'):
							notification_str += 'Modified ' + str(diff_modified.a_blob.path) + "\n"
						os.system(self.remoteNotification.format(shellquote(notification_str)))
				remote.pull()
				remote.push()
		except AttributeError:
			pass


if __name__ == '__main__':
	fs = GitFuse()
	fs.parse(errex=1)
	fs.multithreaded = True
	fs.main()
