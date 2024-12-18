from errno import ENOENT, EXDEV
from os import F_OK, R_OK, W_OK, access, chmod, link, listdir, makedirs, mkdir, readlink, remove, rename, rmdir, sep, stat, statvfs, symlink, utime, walk
from os.path import basename, exists, getsize, isdir, isfile, islink, join as pathjoin, splitext
from re import compile, split
from shutil import copy2
from stat import S_IMODE
from sys import _getframe as getframe
from tempfile import mkstemp
from traceback import print_exc
from xml.etree.ElementTree import Element, fromstring, parse
from unicodedata import normalize
from enigma import eEnv, eGetEnigmaDebugLvl
import os
DEFAULT_MODULE_NAME = __name__.split(".")[-1]

forceDebug = eGetEnigmaDebugLvl() > 4
pathExists = exists

SCOPE_HOME = 0  # DEBUG: Not currently used in Enigma2.
SCOPE_LANGUAGE = 1
SCOPE_KEYMAPS = 2
SCOPE_METADIR = 3
SCOPE_SKINS = 4
SCOPE_GUISKIN = 5
SCOPE_LCDSKIN = 6
SCOPE_FONTS = 7
SCOPE_PLUGINS = 8
SCOPE_PLUGIN = 9
SCOPE_PLUGIN_ABSOLUTE = 10
SCOPE_PLUGIN_RELATIVE = 11
SCOPE_SYSETC = 12
SCOPE_TRANSPONDERDATA = 13
SCOPE_CONFIG = 14
SCOPE_PLAYLIST = 15
SCOPE_MEDIA = 16
SCOPE_HDD = 17
SCOPE_TIMESHIFT = 18
SCOPE_DEFAULTDIR = 19
SCOPE_LIBDIR = 20

# Deprecated scopes:
SCOPE_ACTIVE_LCDSKIN = SCOPE_LCDSKIN
SCOPE_ACTIVE_SKIN = SCOPE_GUISKIN
SCOPE_CURRENT_LCDSKIN = SCOPE_LCDSKIN
SCOPE_CURRENT_PLUGIN = SCOPE_PLUGIN
SCOPE_CURRENT_SKIN = SCOPE_GUISKIN
SCOPE_SKIN = SCOPE_SKINS
SCOPE_SKIN_IMAGE = SCOPE_SKINS
SCOPE_USERETC = SCOPE_HOME

PATH_CREATE = 0
PATH_DONTCREATE = 1

defaultPaths = {
	SCOPE_HOME: ("", PATH_DONTCREATE),  # User home directory
	SCOPE_LANGUAGE: (eEnv.resolve("${datadir}/enigma2/po/"), PATH_DONTCREATE),
	SCOPE_KEYMAPS: (eEnv.resolve("${datadir}/keymaps/"), PATH_CREATE),
	SCOPE_METADIR: (eEnv.resolve("${datadir}/meta/"), PATH_CREATE),
	SCOPE_SKINS: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_GUISKIN: (eEnv.resolve("${datadir}/enigma2/"), PATH_DONTCREATE),
	SCOPE_LCDSKIN: (eEnv.resolve("${datadir}/enigma2/display/"), PATH_DONTCREATE),
	SCOPE_FONTS: (eEnv.resolve("${datadir}/fonts/"), PATH_DONTCREATE),
	SCOPE_PLUGINS: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_CREATE),
	SCOPE_PLUGIN: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_CREATE),
	SCOPE_PLUGIN_ABSOLUTE: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_DONTCREATE),
	SCOPE_PLUGIN_RELATIVE: (eEnv.resolve("${libdir}/enigma2/python/Plugins/"), PATH_DONTCREATE),
	SCOPE_SYSETC: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_TRANSPONDERDATA: (eEnv.resolve("${sysconfdir}/"), PATH_DONTCREATE),
	SCOPE_CONFIG: (eEnv.resolve("${sysconfdir}/enigma2/"), PATH_CREATE),
	SCOPE_PLAYLIST: (eEnv.resolve("${sysconfdir}/enigma2/playlist/"), PATH_CREATE),
	SCOPE_MEDIA: ("/media/", PATH_DONTCREATE),
	SCOPE_HDD: ("/media/hdd/movie/", PATH_DONTCREATE),
	SCOPE_TIMESHIFT: ("/media/hdd/timeshift/", PATH_DONTCREATE),
	SCOPE_DEFAULTDIR: (eEnv.resolve("${datadir}/enigma2/defaults/"), PATH_CREATE),
	SCOPE_LIBDIR: (eEnv.resolve("${libdir}/"), PATH_DONTCREATE)
}

scopeConfig = defaultPaths[SCOPE_CONFIG][0]
scopeGUISkin = defaultPaths[SCOPE_GUISKIN][0]
scopeLCDSkin = defaultPaths[SCOPE_LCDSKIN][0]
scopeFonts = defaultPaths[SCOPE_FONTS][0]
scopePlugins = defaultPaths[SCOPE_PLUGINS][0]


def addInList(*paths):
	return [path for path in paths if os.path.isdir(path)]


skinResolveList = []
lcdskinResolveList = []
fontsResolveList = []


def comparePaths(leftPath, rightPath):
	print("[Directories] comparePaths DEBUG: left='%s', right='%s'." % (leftPath, rightPath))
	if leftPath.endswith(sep):
		leftPath = leftPath[:-1]
	left = leftPath.split(sep)
	right = rightPath.split(sep)
	for index, segment in enumerate(left):
		if left[index] != right[index]:
			return False
	return True


def InitDefaultPaths():
	resolveFilename(SCOPE_CONFIG)


def resolveFilename(scope, base="", path_prefix=None):
	if str(base).startswith("~%s" % os.sep):  # You can only use the ~/ if we have a prefix directory.
		if path_prefix:
			base = os.path.join(path_prefix, base[2:])
		else:
			print("[Directories] Warning: resolveFilename called with base starting with '~%s' but 'path_prefix' is None!" % os.sep)
	if str(base).startswith(os.sep):  # Don't further resolve absolute paths.
		return os.path.normpath(base)
	if scope not in defaultPaths:  # If an invalid scope is specified log an error and return None.
		print("[Directories] Error: Invalid scope=%s provided to resolveFilename!" % scope)
		return None
	path, flag = defaultPaths[scope]  # Ensure that the defaultPath directory that should exist for this scope does exist.
	if flag == PATH_CREATE and not pathExists(path):
		try:
			os.makedirs(path)
		except (IOError, OSError) as err:
			print("[Directories] Error %d: Couldn't create directory '%s'!  (%s)" % (err.errno, path, err.strerror))
			return None
	suffix = None  # Remove any suffix data and restore it at the end.
	data = base.split(":", 1)
	if len(data) > 1:
		base = data[0]
		suffix = data[1]
	path = base

	def itemExists(resolveList, base):
		baseList = [base]
		if base.endswith(".png"):
			baseList.append("%s%s" % (base[:-3], "svg"))
		elif base.endswith(".svg"):
			baseList.append("%s%s" % (base[:-3], "png"))
		for item in resolveList:
			for base in baseList:
				file = os.path.join(item, base)
				if pathExists(file):
					return file
		return base

	if base == "":  # If base is "" then set path to the scope.  Otherwise use the scope to resolve the base filename.
		path, flags = defaultPaths[scope]
		if scope == SCOPE_GUISKIN:  # If the scope is SCOPE_GUISKIN append the current skin to the scope path.
			from Components.config import config  # This import must be here as this module finds the config file as part of the config initialisation.
			skin = os.path.dirname(config.skin.primary_skin.value)
			path = os.path.join(path, skin)
		elif scope in (SCOPE_PLUGIN_ABSOLUTE, SCOPE_PLUGIN_RELATIVE):
			callingCode = os.path.normpath(getframe(1).f_code.co_filename)
			plugins = os.path.normpath(scopePlugins)
			path = None
			if comparePaths(plugins, callingCode):
				pluginCode = callingCode[len(plugins) + 1:].split(os.sep)
				if len(pluginCode) > 2:
					relative = "%s%s%s" % (pluginCode[0], os.sep, pluginCode[1])
					path = os.path.join(plugins, relative)
	elif scope == SCOPE_GUISKIN:
		global skinResolveList
		if not skinResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			skin = os.path.dirname(config.skin.primary_skin.value)
			skinResolveList = addInList(
				os.path.join(scopeConfig, skin),
				os.path.join(scopeConfig, "skin_common"),
				scopeConfig,
				os.path.join(scopeGUISkin, skin),

				os.path.join(scopeGUISkin, "skin_default"),
				scopeGUISkin
			)
		path = itemExists(skinResolveList, base)
	elif scope == SCOPE_LCDSKIN:
		global lcdskinResolveList
		if not lcdskinResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			if hasattr(config.skin, "display_skin"):
				skin = os.path.dirname(config.skin.display_skin.value)
			else:
				skin = ""
			lcdskinResolveList = addInList(
				os.path.join(scopeConfig, "display", skin),
				os.path.join(scopeConfig, "display", "skin_common"),
				scopeConfig,
				os.path.join(scopeLCDSkin, skin),

				os.path.join(scopeLCDSkin, "skin_default"),
				scopeLCDSkin
			)
		path = itemExists(lcdskinResolveList, base)
	elif scope == SCOPE_FONTS:
		global fontsResolveList
		if not fontsResolveList:
			# This import must be here as this module finds the config file as part of the config initialisation.
			from Components.config import config
			skin = os.path.dirname(config.skin.primary_skin.value)
			display = os.path.dirname(config.skin.display_skin.value) if hasattr(config.skin, "display_skin") else None
			fontsResolveList = addInList(
				os.path.join(scopeConfig, "fonts"),
				os.path.join(scopeConfig, skin, "fonts"),
				os.path.join(scopeConfig, skin)
			)
			if display:
				fontsResolveList += addInList(
					os.path.join(scopeConfig, "display", display, "fonts"),
					os.path.join(scopeConfig, "display", display)
				)
			fontsResolveList += addInList(
				os.path.join(scopeConfig, "skin_common"),
				scopeConfig,
				os.path.join(scopeGUISkin, skin, "fonts"),
				os.path.join(scopeGUISkin, skin),
				os.path.join(scopeGUISkin, "skin_default", "fonts"),
				os.path.join(scopeGUISkin, "skin_default")
			)
			if display:
				fontsResolveList += addInList(
					os.path.join(scopeLCDSkin, display, "fonts"),
					os.path.join(scopeLCDSkin, display)
				)
			fontsResolveList += addInList(
				os.path.join(scopeLCDSkin, "skin_default", "fonts"),
				os.path.join(scopeLCDSkin, "skin_default"),
				scopeFonts
			)
		path = itemExists(fontsResolveList, base)
	elif scope == SCOPE_PLUGIN:
		file = os.path.join(scopePlugins, base)
		if pathExists(file):
			path = file
	elif scope in (SCOPE_PLUGIN_ABSOLUTE, SCOPE_PLUGIN_RELATIVE):
		callingCode = os.path.normpath(getframe(1).f_code.co_filename)
		plugins = os.path.normpath(scopePlugins)
		path = None
		if comparePaths(plugins, callingCode):
			pluginCode = callingCode[len(plugins) + 1:].split(os.sep)
			if len(pluginCode) > 2:
				relative = os.path.join("%s%s%s" % (pluginCode[0], os.sep, pluginCode[1]), base)
				path = os.path.join(plugins, relative)
	else:
		path, flags = defaultPaths[scope]
		path = os.path.join(path, base)
	path = os.path.normpath(path)
	if os.path.isdir(path) and not path.endswith(os.sep):  # If the path is a directory then ensure that it ends with a "/".
		path = "%s%s" % (path, os.sep)
	if scope == SCOPE_PLUGIN_RELATIVE:
		path = path[len(plugins) + 1:]
	if suffix is not None:  # If a suffix was supplied restore it.
		path = "%s:%s" % (path, suffix)
	return path


def bestRecordingLocation(candidates):
	path = ""
	biggest = 0
	for candidate in candidates:
		try:
			status = statvfs(candidate[1])  # Must have some free space (i.e. not read-only).
			if status.f_bavail:
				size = (status.f_blocks + status.f_bavail) * status.f_bsize  # Free space counts double.
				if size > biggest:
					biggest = size
					path = candidate[1]
		except OSError as err:
			print("[Directories] Error %d: Couldn't get free space for '%s'!  (%s)" % (err.errno, candidate[1], err.strerror))
	return path


def defaultRecordingLocation(candidate=None):
	if candidate and pathExists(candidate):
		return candidate
	try:
		path = readlink("/hdd")  # First, try whatever /hdd points to, or /media/hdd.
	except OSError as err:
		print(err)
		path = "/media/hdd"
	if not pathExists(path):  # Find the largest local disk.
		from Components import Harddisk
		mounts = [mount for mount in Harddisk.getProcMounts() if mount[1].startswith("/media/")]
		path = bestRecordingLocation([mount for mount in mounts if mount[0].startswith("/dev/")])  # Search local devices first, use the larger one.
		if not path:  # If we haven't found a viable candidate yet, try remote mounts.
			path = bestRecordingLocation([mount for mount in mounts if not mount[0].startswith("/dev/")])
	if path:
		movie = pathjoin(path, "movie", "")  # If there's a movie subdir, we'd probably want to use that (directories need to end in sep).
		if isdir(movie):
			path = movie
	return path


def createDir(path, makeParents=False):
	try:
		if makeParents:
			makedirs(path)
		else:
			mkdir(path)
		return 1
	except OSError as err:
		print("[Directories] Error %d: Couldn't create directory '%s'!  (%s)" % (err.errno, path, err.strerror))
	return 0


def fileReadLine(filename, default=None, source=DEFAULT_MODULE_NAME, debug=False):
	line = None
	try:
		with open(filename) as fd:
			line = fd.read().strip().replace("\0", "")
		msg = "Read"
	except OSError as err:
		if err.errno != ENOENT:  # ENOENT - No such file or directory.
			print("[%s] Error %d: Unable to read a line from file '%s'!  (%s)" % (source, err.errno, filename, err.strerror))
		line = default
		# msg = "Default"
	# if debug or forceDebug:
		# print("[%s] Line %d: %s '%s' from file '%s'." % (source, getframe(1).f_lineno, msg, line, filename))
	return line


def removeDir(path):
	try:
		rmdir(path)
		return 1
	except OSError as err:
		print("[Directories] Error %d: Couldn't remove directory '%s'!  (%s)" % (err.errno, path, err.strerror))
	return 0


def fileExists(file, mode="r"):
	return fileAccess(file, mode) and file


def fileCheck(file, mode="r"):
	return fileAccess(file, mode) and file


def fileDate(f):
	if fileExists(f):
		import datetime
		return datetime.fromtimestamp(os.stat(f).st_mtime).strftime("%Y-%m-%d")
	return ("1970-01-01")


def fileHas(file, content, mode="r"):
	return fileContains(file, content, mode)


def fileReadXML(filename, default=None, *args, **kwargs):
	dom = None
	try:
		with open(filename, "r", encoding="utf-8") as fd:
			dom = parse(fd).getroot()
	except:
		print("[fileReadXML] failed to read", filename)
		print_exc()
	if dom is None and default:
		if isinstance(default, str):
			dom = fromstring(default)
		elif isinstance(default, Element):
			dom = default
	return dom


def getRecordingFilename(basename, dirname=None):
	nonAllowedCharacters = "/.\\:*?<>|\""  # Filter out non-allowed characters.

	basename = basename.replace("\x86", "").replace("\x87", "")
	filename = ""
	for character in basename:
		if character in nonAllowedCharacters or ord(character) < 32:
			character = "_"
		filename += character
	# Max filename length for ext4 is 255 (minus 8 characters for .ts.meta)
	# but must not truncate in the middle of a multi-byte utf8 character!
	# So convert the truncation to unicode and back, ignoring errors, the
	# result will be valid utf8 and so xml parsing will be OK.
	filename = filename[:247]
	if dirname is None:
		dirname = defaultRecordingLocation()
	else:
		if not dirname.startswith(sep):
			dirname = pathjoin(defaultRecordingLocation(), dirname)
	filename = pathjoin(dirname, filename)
	next = 0
	path = filename
	while isfile("%s.ts" % path):
		next += 1
		path = "%s_%03d" % (filename, next)
	return path


def InitFallbackFiles():
	resolveFilename(SCOPE_CONFIG, "userbouquet.favourites.tv")
	resolveFilename(SCOPE_CONFIG, "bouquets.tv")
	resolveFilename(SCOPE_CONFIG, "userbouquet.favourites.radio")
	resolveFilename(SCOPE_CONFIG, "bouquets.radio")


# Returns a list of tuples containing pathname and filename matching the given pattern
# Example-pattern: match all txt-files: ".*\.txt$"


def crawlDirectory(directory, pattern):
	fileList = []
	if directory:
		expression = compile(pattern)
		for root, dirs, files in walk(directory):
			for file in files:
				if expression.match(file) is not None:
					fileList.append((root, file))
	return fileList


def copyFile(src, dst):
	try:
		copy2(src, dst)
	except OSError as err:
		print("[Directories] Error %d: Copying file '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
		return -1
	return 0
	# if isdir(dst):
	#   dst = pathjoin(dst, basename(src))
	# try:
	#   with open(src, "rb") as fd1:
	#       with open(dst, "w+b") as fd2:
	#           while True:
	#               buf = fd1.read(16 * 1024)
	#               if not buf:
	#                   break
	#               fd2.write(buf)
	#   try:
	#       status = stat(src)
	#       try:
	#           chmod(dst, S_IMODE(status.st_mode))
	#       except OSError as err:
	#           print("[Directories] Error %d: Setting modes from '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
	#       try:
	#           utime(dst, (status.st_atime, status.st_mtime))
	#       except OSError as err:
	#           print("[Directories] Error %d: Setting times from '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
	#   except OSError as err:
	#       print("[Directories] Error %d: Obtaining status from '%s'!  (%s)" % (err.errno, src, err.strerror))
	# except OSError as err:
	#   print("[Directories] Error %d: Copying file '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
	#   return -1
	# return 0


def copyfile(src, dst):
	return copyFile(src, dst)


def copytree(src, dst, symlinks=False):
	return copyTree(src, dst, symlinks=symlinks)


def copyTree(src, dst, symlinks=False):
	names = listdir(src)
	if isdir(dst):
		dst = pathjoin(dst, basename(src))
		if not isdir(dst):
			mkdir(dst)
	else:
		makedirs(dst)
	for name in names:
		srcName = pathjoin(src, name)
		dstName = pathjoin(dst, name)
		try:
			if symlinks and islink(srcName):
				linkTo = readlink(srcName)
				symlink(linkTo, dstName)
			elif isdir(srcName):
				copytree(srcName, dstName, symlinks)
			else:
				copyfile(srcName, dstName)
		except OSError as err:
			print("[Directories] Error %d: Copying tree '%s' to '%s'!  (%s)" % (err.errno, srcName, dstName, err.strerror))
	try:
		status = stat(src)
		try:
			chmod(dst, S_IMODE(status.st_mode))
		except OSError as err:
			print("[Directories] Error %d: Setting modes from '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
		try:
			utime(dst, (status.st_atime, status.st_mtime))
		except OSError as err:
			print("[Directories] Error %d: Setting times from '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))
	except OSError as err:
		print("[Directories] Error %d: Obtaining stats from '%s' to '%s'!  (%s)" % (err.errno, src, dst, err.strerror))


# Renames files or if source and destination are on different devices moves them in background
# input list of (source, destination)


def moveFiles(fileList):
	errorFlag = False
	movedList = []
	try:
		for item in fileList:
			rename(item[0], item[1])
			movedList.append(item)
	except OSError as err:
		if err.errno == EXDEV:  # EXDEV - Invalid cross-device link.
			print("[Directories] Warning: Cannot rename across devices, trying slower move.")
			from Tools.CopyFiles import moveFiles as extMoveFiles  # OpenViX, OpenATV, Beyonwiz
			# from Screens.CopyFiles import moveFiles as extMoveFiles  # OpenPLi / OV
			extMoveFiles(fileList, item[0])
			print("[Directories] Moving files in background.")
		else:
			print("[Directories] Error %d: Moving file '%s' to '%s'!  (%s)" % (err.errno, item[0], item[1], err.strerror))
			errorFlag = True
	if errorFlag:
		print("[Directories] Reversing renamed files due to error.")
		for item in movedList:
			try:
				rename(item[1], item[0])
			except OSError as err:
				print("[Directories] Error %d: Renaming '%s' to '%s'!  (%s)" % (err.errno, item[1], item[0], err.strerror))
				print("[Directories] Note: Failed to undo move of '%s' to '%s'!" % (item[0], item[1]))


def getSize(path, pattern=".*"):
	pathSize = 0
	if isdir(path):
		for file in crawlDirectory(path, pattern):

			pathSize += getsize(pathjoin(file[0], file[1]))

	elif isfile(path):
		pathSize = getsize(path)
	return pathSize


def lsof():  # List of open files.
	lsof = []
	for pid in listdir("/proc"):
		if pid.isdigit():
			try:
				prog = readlink(pathjoin("/proc", pid, "exe"))
				dir = pathjoin("/proc", pid, "fd")
				for file in [pathjoin(dir, file) for file in listdir(dir)]:
					lsof.append((pid, prog, readlink(file)))
			except OSError as err:
				print(err)
				pass
	return lsof


def getExtension(file):
	filename, extension = splitext(file)
	return extension


def mediafilesInUse(session):
	from Components.MovieList import KNOWN_EXTENSIONS
	TRANSMISSION_PART = fileExists("/usr/bin/transmission-daemon") and os.popen("pidof transmission-daemon").read() and ".part" or "N/A"
	files = [os.path.basename(x[2]) for x in lsof() if getExtension(x[2]) in (KNOWN_EXTENSIONS, TRANSMISSION_PART)]
	service = session.nav.getCurrentlyPlayingServiceOrGroup()
	filename = service and service.getPath()
	if filename:
		if "://" in filename:  # When path is a stream ignore it.
			filename = None
		else:
			filename = os.path.basename(filename)
	return set([file for file in files if not (filename and file == filename and files.count(filename) < 2)])


def shellQuote(string):
	return "'%s'" % string.replace("'", "'\\''")


def shellquote(string):
	return shellQuote(string)


def isPluginInstalled(pluginName, pluginFile="plugin", pluginType=None):
	types = ["Extensions", "SystemPlugins"]
	if pluginType:
		types = [pluginType]
	for type in types:
		for extension in ["c", ""]:
			if isfile(pathjoin(scopePlugins, type, pluginName, "%s.py%s" % (pluginFile, extension))):
				return True
	return False


def fileWriteLine(filename, line, source=DEFAULT_MODULE_NAME, debug=False):
	try:
		with open(filename, "w") as fd:
			fd.write(str(line))
		msg = "Wrote"
		result = 1
	except OSError as err:
		print("[%s] Error %d: Unable to write a line to file '%s'!  (%s)" % (source, err.errno, filename, err.strerror))
		# msg = "Failed to write"
		result = 0
	# if debug or forceDebug:
		# print("[%s] Line %d: %s '%s' to file '%s'." % (source, getframe(1).f_lineno, msg, line, filename))
	return result


def fileUpdateLine(filename, conditionValue, replacementValue, create=False, source=DEFAULT_MODULE_NAME, debug=False):
	line = fileReadLine(filename, default="", source=source, debug=debug)
	create = False if conditionValue and not line.startswith(conditionValue) else create
	return fileWriteLine(filename, replacementValue, source=source, debug=debug) if create or (conditionValue and line.startswith(conditionValue)) else 0


def fileReadLines(filename, default=None, source=DEFAULT_MODULE_NAME, debug=False):
	lines = None
	try:
		with open(filename) as fd:
			lines = fd.read().splitlines()
		msg = "Read"
	except OSError as err:
		if err.errno != ENOENT:  # ENOENT - No such file or directory.
			print("[%s] Error %d: Unable to read lines from file '%s'!  (%s)" % (source, err.errno, filename, err.strerror))
		lines = default
		# msg = "Default"
	# if debug or forceDebug:
		# length = len(lines) if lines else 0
		# print("[%s] Line %d: %s %d lines from file '%s'." % (source, getframe(1).f_lineno, msg, length, filename))
	return lines


def fileWriteLines(filename, lines, source=DEFAULT_MODULE_NAME, debug=False):
	try:
		with open(filename, "w") as fd:
			if isinstance(lines, list):
				lines.append("")
				lines = "\n".join(lines)
			fd.write(lines)
		msg = "Wrote"
		result = 1
	except OSError as err:
		print("[%s] Error %d: Unable to write %d lines to file '%s'!  (%s)" % (source, err.errno, len(lines), filename, err.strerror))
		msg = "Failed to write"
		# result = 0
	# if debug or forceDebug:
		# print("[%s] Line %d: %s %d lines to file '%s'." % (source, getframe(1).f_lineno, msg, len(lines), filename))
	return result


def fileAccess(file, mode="r"):
	accMode = F_OK
	if "r" in mode:
		accMode |= R_OK
	if "w" in mode:
		accMode |= W_OK
	result = False
	try:
		result = access(file, accMode)
	except OSError as err:
		print("[Directories] Error %d: Couldn't determine file '%s' access mode!  (%s)" % (err.errno, file, err.strerror))
	return result


def fileContains(file, content, mode="r"):
	result = False
	if fileExists(file, mode):
		with open(file, mode) as fd:
			text = fd.read()
		if content in text:
			result = True
	return result


def renameDir(oldPath, newPath):
	try:
		rename(oldPath, newPath)
		return 1
	except OSError as err:
		print("[Directories] Error %d: Couldn't rename directory '%s' to '%s'!  (%s)" % (err.errno, oldPath, newPath, err.strerror))
	return 0


def hasHardLinks(path):  # Test if the volume containing path supports hard links.
	try:
		fd, srcName = mkstemp(prefix="HardLink_", suffix=".test", dir=path, text=False)
	except OSError as err:
		print("[Directories] Error %d: Creating temp file!  (%s)" % (err.errno, err.strerror))
		return False
	dstName = "%s.link" % splitext(srcName)[0]
	try:
		link(srcName, dstName)
		result = True
	except OSError as err:
		print("[Directories] Error %d: Creating hard link!  (%s)" % (err.errno, err.strerror))
		result = False
	try:
		remove(srcName)
	except OSError as err:
		print("[Directories] Error %d: Removing source file!  (%s)" % (err.errno, err.strerror))
	try:
		remove(dstName)
	except OSError as err:
		print("[Directories] Error %d: Removing destination file!  (%s)" % (err.errno, err.strerror))
	return result


def sanitizeFilename(filename):
	"""Return a fairly safe version of the filename.

	We don't limit ourselves to ascii, because we want to keep municipality
	names, etc, but we do want to get rid of anything potentially harmful,
	and make sure we do not exceed Windows filename length limits.
	Hence a less safe blacklist, rather than a whitelist.
	"""
	blacklist = ["\\", "/", ":", "*", "?", "\"", "<", ">", "|", "\0", "(", ")", " "]
	reserved = [
		"CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
		"COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5",
		"LPT6", "LPT7", "LPT8", "LPT9",
	]  # Reserved words on Windows
	filename = "".join(c for c in filename if c not in blacklist)
	# Remove all charcters below code point 32
	filename = "".join(c for c in filename if 31 < ord(c))
	filename = normalize("NFKD", filename)
	filename = filename.rstrip(". ")  # Windows does not allow these at end
	filename = filename.strip()
	if all([x == "." for x in filename]):
		filename = "__" + filename
	if filename in reserved:
		filename = "__" + filename
	if len(filename) == 0:
		filename = "__"
	if len(filename) > 255:
		parts = split(r"/|\\", filename)[-1].split(".")
		if len(parts) > 1:
			ext = "." + parts.pop()
			filename = filename[:-len(ext)]
		else:
			ext = ""
		if filename == "":
			filename = "__"
		if len(ext) > 254:
			ext = ext[254:]
		maxl = 255 - len(ext)
		filename = filename[:maxl]
		filename = filename + ext
		# Re-check last character (if there was no extension)
		filename = filename.rstrip(". ")
		if len(filename) == 0:
			filename = "__"
	return filename
