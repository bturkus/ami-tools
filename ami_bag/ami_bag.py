import os, csv, re, logging

import ami_bag.update_bag as update_bag
import bagit

# ami modules
import ami_bag.ami_bag_constants as ami_bag_constants
from ami_md.ami_excel import ami_excel
import ami_md.ami_json as aj


LOGGER = logging.getLogger(__name__)

class ami_BagError(Exception):
    pass

class ami_bagValidationError(ami_BagError):
    def __init__(self, message):
        self.message = message
    def __str__(self):
        return repr(self.message)

class ami_bag(update_bag.Repairable_Bag):

    def __init__(self, *args, **kwargs):
        super(ami_bag, self).__init__(*args, **kwargs)

        try:
            self.validate(completeness_only = True)
        except bagit.BagValidationError as e:
            raise ami_BagError("Unable to load bag, oxum or manifest is invalid")

        self.data_files = set(self.payload_entries().keys())
        self.data_exts = set([os.path.splitext(filename)[1].lower() for filename in self.data_files])

        self.data_dirs = set([os.path.split(path)[0][5:] for path in self.data_files])
        if "PreservationMasters" not in self.data_dirs:
            raise ami_BagError("Payload does not contain a PreservationMasters directory")

        self.media_filepaths = set([os.path.join(self.path, path) for
            path in self.data_files if any(path.lower().endswith(ext) for ext in ami_bag_constants.MEDIA_EXTS)])
        if not self.media_filepaths:
            raise ami_BagError("Payload does not contain files with accepted extensions: {}".format(
                ami_bag_constants.MEDIA_EXTS
            ))

        self.set_type()
        if self.type == "excel":
            self.set_subtype_excel()
            self.set_metadata_excel()
        if self.type == "json":
            self.set_subtype_json()
            self.set_metadata_json()
        if self.type == "excel-json":
            self.set_subtype_exceljson()
            self.set_metadata_json()

        LOGGER.info("{} successfully loaded as {} {} bag".format(
            self.path, self.type, self.subtype
        ))


    def validate_amibag(self, fast = True, metadata = False):
        '''
        run each of the validation checks against an AMI Bag
        '''

        valid = True
        try:
            self.validate(fast = fast, completeness_only = fast)
        except bagit.BagValidationError as e:
            LOGGER.warning("Error in bag: {0}".format(e.message))
            valid = False

        try:
            self.check_filenames()
        except ami_bagValidationError as e:
            LOGGER.warning("Error in filenames: {0}".format(e.message))
            valid = False

        try:
            self.check_simple_filenames()
        except ami_bagValidationError as e:
            LOGGER.warning("Error in filenames: {0}".format(e.message))
            valid = False

        try:
            self.check_directory_depth()
        except ami_bagValidationError as e:
            LOGGER.error("Error in path names: {0}".format(e.message))
            valid = False

        try:
            self.check_type()
        except ami_bagValidationError as e:
            LOGGER.error("Error in AMI bag type: {0}".format(e.message))
            valid = False

        if self.type == "excel":
            try:
                self.check_bagstructure_excel()
            except ami_bagValidationError as e:
                LOGGER.error("Error in bag structure: {0}".format(e.message))
                valid = False

            if metadata:
                try:
                    self.check_metadata_excel()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in bag metadata: {0}".format(e.message))
                    valid = False

                try:
                    self.check_filenames_manifest_and_metadata_excel()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in bag metadata: {0}".format(e.message))
                    valid = False

        else:
            if self.type == "json":
                try:
                    self.check_bagstructure_json()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in AMI bag type: {0}".format(e.message))
                    valid = False

            elif self.type == "excel-json":
                try:
                    self.check_bagstructure_exceljson()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in AMI bag type: {0}".format(e.message))
                    valid = False

            if metadata:
                try:
                    self.check_metadata_json()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in bag metadata: {0}".format(e.message))
                    valid = False

                try:
                    self.check_filenames_manifest_and_metadata_json()
                except ami_bagValidationError as e:
                    LOGGER.error("Error in bag metadata: {0}".format(e.message))
                    valid = False

        return valid


    def check_filenames(self):
        bad_filenames = []

        for filepath in self.data_files:
            filename = os.path.split(filepath)[1]
            if not ami_bag_constants.FILENAME_REGEX.search(filename):
                bad_filenames.append(filename)

        if bad_filenames:
            self.raise_bagerror("Non-standard filenames for the following: {}".format(bad_filenames))

        return True


    def check_simple_filenames(self):
        complex_filenames = []

        for filepath in self.data_files:
            filename = os.path.split(filepath)[1]
            if ami_bag_constants.SUBOBJECT_REGEX.search(filename):
                complex_filenames.append(filename)

        if complex_filenames:
            self.raise_bagerror("Complex digitized objects represented by: {}".format(complex_filenames))

        return True


    def check_directory_depth(self):
        bad_dirs = []

        for dir_path in self.data_dirs:
            if re.search(r"/", dir_path):
                bad_dirs.append(dir_path)

        if bad_dirs:
            self.raise_bagerror("Too many levels of directories in data/: {}".format(bad_dirs))

        return True


    def set_type(self):
        self.type = None

        if "Metadata" in self.data_dirs:
            self.type = "excel"
        if ".json" in self.data_exts:
            if self.type == "excel":
                self.type = "excel-json"
            else:
                self.type = "json"

        if not self.type:
            raise ami_BagError("AMI bag must contain either Excel or JSON metadata")

        return True


    def check_type(self):
        if not self.type:
            raise ami_BagError("Bag is not an Excel bag or JSON bag")

        return True


    def compare_content(self, expected_exts):
        if not expected_exts >= self.data_exts:
            return False
        return True


    def compare_structure(self, expected_dirs):
        if not expected_dirs >= self.data_dirs:
            return False
        return True


    def set_subtype_excel(self):
        self.subtype = None

        if (self.compare_structure(set(["Metadata", "PreservationMasters"])) and
            self.compare_content(set([".mov", ".xlsx", ".old"]))):
            self.subtype = "video"
        elif (self.compare_structure(set(["Metadata", "PreservationMasters"])) and
              self.compare_content(set([".iso", ".xlsx", ".old"]))):
            self.subtype = "dvd"
        elif (self.compare_structure(set(["Metadata", "PreservationMasters", "EditMasters"])) and
              self.compare_content(set([".wav", ".xlsx", ".old"]))):
            self.subtype = "audio"
        elif (self.compare_structure(set(["Metadata", "PreservationMasters"])) and
              self.compare_content(set([".wav", ".xlsx", ".old"]))):
            self.subtype = "audio w/o edit masters"
        elif (self.compare_structure(set(["Metadata", "ArchiveOriginals", "PreservationMasters", "EditMasters", "ProjectFiles", "ProjectFile"])) and
              self.compare_content(set([".tar", ".mov", ".xlsx", ".fcp", ".prproj"]))):
            self.subtype = "born-digital video"
        elif (self.compare_structure(set(["Metadata", "ArchiveOriginals", "EditMasters"])) and
              self.compare_content(set([".wav", ".xlsx", ".old"]))):
            self.subtype = "born-digital audio"

        return True


    def check_bagstructure_excel(self):
        expected_dirs = set(["Metadata", "PreservationMasters", "EditMasters", "ArchiveOriginals", "ProjectFiles"])
        if not self.compare_structure(expected_dirs):
            self.raise_bagerror("AMI Excel bags may only have the following directories\nFound: {0}\nExpected: {1}".format(self.data_dirs, expected_dirs))

        if not self.subtype:
            self.raise_bagerror("Bag does not match an existing profile for AMI Excel bags\nExtensions Found: {0}\nDirectories Found: {1}".format(self.data_exts, self.data_dirs))

        return True


    def set_subtype_json(self):
        self.subtype = None

        if (self.compare_structure(set(["Metadata", "PreservationMasters", "ServiceCopies", "Images"])) and
            self.compare_content(set([".mov", ".json", ".mp4", ".jpeg", ".jpg"]))):
            self.subtype = "video"
        elif (self.compare_structure(set(["Metadata", "PreservationMasters", "EditMasters", "Images"])) and
            self.compare_content(set([".wav", ".json", ".jpeg", ".jpg"]))):
            self.subtype = "audio"

        return True


    def check_bagstructure_json(self):
        expected_dirs = set(["PreservationMasters", "ServiceCopies", "EditMasters", "Images"])

        if not self.compare_structure(expected_dirs):
            self.raise_bagerror("JSON bags may only have the following directories - {}".format(expected_dirs))

        if not self.subtype:
            self.raise_bagerror("Bag does not match an existing profile for JSON bags\nExtensions Found: {0}\nDirectories Found: {1}".format(self.data_exts, self.data_dirs))

        return True


    def set_subtype_exceljson(self):
        self.subtype = None

        if (self.compare_structure(set(["Metadata", "PreservationMasters", "ServiceCopies", "Images"])) and
            self.compare_content(set([".mov", ".xlsx", ".json", ".mp4", ".jpeg"]))):
            self.subtype = "video"
        elif (self.compare_structure(set(["Metadata", "PreservationMasters", "EditMasters", "Images"])) and
            self.compare_content(set([".wav", ".xlsx", ".json", ".jpeg"]))):
            self.subtype = "audio"

        return True


    def check_bagstructure_exceljson(self):
        expected_dirs = set(["Metadata", "PreservationMasters", "ServiceCopies", "EditMasters", "ArchiveOriginals"])

        if not self.compare_structure(expected_dirs):
            self.raise_bagerror("Excel JSON bags may only have the following directories - {}".format(expected_dirs))

        if not self.subtype:
            self.raise_bagerror("Bag does not match an existing profile for Excel JSON bags\nExtensions Found: {0}\nDirectories Found: {1}".format(self.data_exts, self.data_dirs))

        return True


    def set_metadata_excel(self):
        self.metadata_files = [filename for filename in self.data_files if os.path.splitext(filename)[1] == ".xlsx"]

        self.media_files_md = []

        for filename in self.metadata_files:
            excel = ami_excel(os.path.join(self.path, filename))

            # collect list of filenames in metadata
            if excel.pres_sheet:
                paths = excel.pres_sheet.sheet_values["asset.referenceFilename"].tolist()
                self.media_files_md.extend(paths)
            if excel.edit_sheet:
                if "asset.referenceFilename" in excel.edit_sheet.sheet_values.columns:
                    paths = excel.edit_sheet.sheet_values["asset.referenceFilename"].tolist()
                    self.media_files_md.extend(paths)

        self.media_files_md = set(self.media_files_md)

        return


    def check_metadata_excel(self):
        if not self.metadata_files:
            self.raise_bagerror("Excel bag does not contain any files with xlsx extension")

        bad_excel = []

        for filename in self.metadata_files:
            excel = ami_excel(os.path.join(self.path, filename))
            if not excel.validate_workbook():
                bad_excel.append(filename)

        if bad_excel:
            self.raise_bagerror("Excel files contain formatting errors")

        return True


    def check_filenames_manifest_and_metadata_excel(self):
        media_files_basenames = set([os.path.splitext(os.path.basename(path))[0] for path in self.media_filepaths])
        if not self.media_files_md >= media_files_basenames:
            self.raise_bagerror("Filenames in Excel do not match filenames in manifest. Missing: {}".format(
                media_files_basenames - self.media_files_md
            ))
        return True


    def set_metadata_json(self):
        self.metadata_files = [filename for filename in self.data_files if os.path.splitext(filename)[1] == ".json"]

        self.media_files_md = []

        for filename in self.metadata_files:
            json = aj.ami_json(filepath = os.path.join(self.path, filename))
            filename = json.dict["technical"]["filename"]
            ext = json.dict["technical"]["extension"]
            self.media_files_md.append(filename + '.' + ext)

        self.media_files_md = set(self.media_files_md)

        return


    def check_metadata_json(self):
        if not self.metadata_files:
            self.raise_bagerror("JSON bag does not contain any files with json extension")

        bad_json = []

        for filename in self.metadata_files:
            json_filepath = os.path.join(self.path, filename)
            json = aj.ami_json(filepath = json_filepath)
            ext = json.dict['technical']['extension']
            json.set_mediafilepath(json_filepath.replace('json', ext))
            try:
                json.validate_json()
            except:
                bad_json.append(filename)

        if bad_json:
            self.raise_bagerror("JSON files contain formatting errors")

        return True


    def check_filenames_manifest_and_metadata_json(self):
        media_files_basenames = set([os.path.basename(path) for path in self.media_filepaths])
        if not self.media_files_md == media_files_basenames:
            self.raise_bagerror("Filenames in JSON do not match filenames in manifest.\nMissing from JSON: {}".format(
                media_files_basenames - self.media_files_md
            ))
        return True


    def add_json_from_excel(self):
        self.excel_metadata = [filename for filename in self.data_files if os.path.splitext(filename)[1] == ".xlsx"]

        for filename in self.excel_metadata:
            excel = ami_excel(os.path.join(self.path, filename))

            if excel.edit_sheet:
                em_path = os.path.join(self.path, "data/EditMasters")
                # TODO where do i error when files don't match
                try:
                    excel.edit_sheet.add_PMDataToEM(excel.pres_sheet.sheet_values)
                except:
                    LOGGER.error("EM's and PM's do not have 1-1 correspondence")
                else:
                    em_filepaths = [x + ".json" for x in self.media_filepaths if em_path in x]
                    excel.edit_sheet.convert_amiExcelToJSON(em_path, filepaths = em_filepaths)

            pm_path = os.path.join(self.path, "data/PreservationMasters")
            pm_filepaths = [x + ".json" for x in self.media_filepaths if pm_path in x]
            excel.pres_sheet.convert_amiExcelToJSON(pm_path, filepaths = pm_filepaths)


    def raise_bagerror(self, msg):
        '''
        lazy error reporting
        '''
        LOGGER.error(msg)
        raise ami_bagValidationError(msg)

        return False



def _configure_logging(args):
    log_format = "%(asctime)s - %(levelname)s - %(message)s"
    if args.quiet:
        level = logging.WARNING
    else:
        level = logging.INFO
    if args.log:
        logging.basicConfig(filename=args.log, level=level, format=log_format)
    else:
        logging.basicConfig(level=level, format=log_format)
