import pickle
import NuRadioReco.framework.event


def scan_files_function(version_major, version_minor):
    """
    Returns the function to scan a file with the given file version
    Convention for function names is scan_files_MAJORVERSION_MINORVERSION,
    specifying the first version that function is for
    """

    def scan_files_2_0(self, iF, current_byte):
        bytes_to_read_hex = self._get_file(iF).read(6)
        bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
        if(bytes_to_read == 0):
            # we are at the end of the file
            if(iF < (len(self._filenames) - 1)):  # are there more files to be parsed?
                iF += 1
                current_byte = 12  # skip datafile header
                self._get_file(iF).seek(current_byte)
                bytes_to_read_hex = self._get_file(iF).read(6)
                bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
                self._bytes_start_header.append([])
                self._bytes_length_header.append([])
                self._bytes_start.append([])
                self._bytes_length.append([])
            else:
                return False, iF, current_byte
        current_byte += 6
        self._bytes_start_header[iF].append(current_byte)
        self._bytes_length_header[iF].append(bytes_to_read)
        current_byte += bytes_to_read

        evt_header = pickle.loads(self._get_file(iF).read(bytes_to_read))
        self._parse_event_header(evt_header)

        self._get_file(iF).seek(current_byte)
        bytes_to_read_hex = self._get_file(iF).read(6)
        current_byte += 6
        bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
        self._bytes_start[iF].append(current_byte)
        self._bytes_length[iF].append(bytes_to_read)
        current_byte += bytes_to_read
        # print("reading event {} with length {} from byte {} onwards".format(len(self.__bytes_length[iF]), bytes_to_read, self.__bytes_start[iF][-1]))
        return True, iF, current_byte

    def scan_files_2_2(self, iF, current_byte):
        object_type_hex = self._get_file(iF).read(6)
        object_type = int.from_bytes(object_type_hex, 'little')
        current_byte += 6
        bytes_to_read_hex = self._get_file(iF).read(6)
        bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
        if(bytes_to_read == 0):
            # we are at the end of the file
            if(iF < (len(self._filenames) - 1)):  # are there more files to be parsed?
                iF += 1
                current_byte = 12  # skip datafile header
                self._get_file(iF).seek(current_byte)
                object_type_hex = self._get_file(iF).read(6)
                object_type = int.from_bytes(object_type_hex, 'little')
                bytes_to_read_hex = self._get_file(iF).read(6)
                bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
                self._bytes_start_header.append([])
                self._bytes_length_header.append([])
                self._bytes_start.append([])
                self._bytes_length.append([])
                current_byte += 6
            else:
                return False, iF, current_byte
        current_byte += 6
        if object_type == 0:  # object is an event
            self._bytes_start_header[iF].append(current_byte)
            self._bytes_length_header[iF].append(bytes_to_read)
            current_byte += bytes_to_read

            evt_header = pickle.loads(self._get_file(iF).read(bytes_to_read))
            self._parse_event_header(evt_header)

            self._get_file(iF).seek(current_byte)
            bytes_to_read_hex = self._get_file(iF).read(6)
            current_byte += 6
            bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
            self._bytes_start[iF].append(current_byte)
            self._bytes_length[iF].append(bytes_to_read)
        elif object_type == 1:  # object is detector info
            detector_dict = pickle.loads(self._get_file(iF).read(bytes_to_read))
            if iF not in self._detector_dicts.keys():
                self._detector_dicts[iF] = {
                    'channels': {},
                    'stations': {}
                }
            for station in detector_dict['stations'].values():
                if len(self._detector_dicts[iF]['stations'].keys()) == 0:
                    index = 0
                else:
                    index = max(self._detector_dicts[iF]['stations'].keys()) + 1
                self._detector_dicts[iF]['stations'][index] = station
            for channel in detector_dict['channels'].values():
                if len(self._detector_dicts[iF]['channels'].keys()) == 0:
                    index = 0
                else:
                    index = max(self._detector_dicts[iF]['channels'].keys()) + 1
                self._detector_dicts[iF]['channels'][index] = channel
        current_byte += bytes_to_read
        return True, iF, current_byte

    if version_major == 2:
        if version_minor < 2:
            return scan_files_2_0
        else:
            return scan_files_2_2
    else:
        raise ValueError('File version {}.{} is not supported. Major version needs to be 2 but is {}'.format(version_major, version_minor, version_major))


def iter_events_function(version_major, version_minor):

    def iter_events_2_0(self):
        while True:
            bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
            bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
            if(bytes_to_read == 0):
                # we are at the end of the file
                if(self._current_file_id < (len(self._filenames) - 1)):  # are there more files to be parsed?
                    self._current_file_id += 1
                    self._get_file(self._current_file_id).seek(12)  # skip datafile header
                    bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
                    bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
                else:
                    break
            evt_header_str = self._get_file(self._current_file_id).read(bytes_to_read)

            bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
            bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
            evtstr = self._get_file(self._current_file_id).read(bytes_to_read)
            event = NuRadioReco.framework.event.Event(0, 0)
            event.deserialize(evtstr)
            yield event

    def iter_events_2_2(self):
        while True:
            object_type_hex = self._get_file(self._current_file_id).read(6)
            object_type = int.from_bytes(object_type_hex, 'little')
            bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
            bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
            if(bytes_to_read == 0):
                # we are at the end of the file
                while(self._current_file_id < (len(self._filenames) - 1)):  # are there more files to be parsed?
                    self._current_file_id += 1
                    if(not self.__check_file_version(self._current_file_id)):
                        self._logger.warning("skipping broken file")
                        continue
                    self._get_file(self._current_file_id).seek(12)  # skip datafile header
                    object_type_hex = self._get_file(self._current_file_id).read(6)
                    object_type = int.from_bytes(object_type_hex, 'little')
                    bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
                    bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
                else:
                    break
            if object_type == 0:
                evt_header_str = self._get_file(self._current_file_id).read(bytes_to_read)
                bytes_to_read_hex = self._get_file(self._current_file_id).read(6)
                bytes_to_read = int.from_bytes(bytes_to_read_hex, 'little')
                evtstr = self._get_file(self._current_file_id).read(bytes_to_read)
                event = NuRadioReco.framework.event.Event(0, 0)
                event.deserialize(evtstr)
                yield event
            elif object_type == 1:
                self._get_file(self._current_file_id).read(bytes_to_read)

    if version_major == 2:
        if version_minor < 2:
            return iter_events_2_0
        else:
            return iter_events_2_2
    else:
        raise ValueError('File version {}.{} is not supported. Major version needs to be 2 but is {}'.format(version_major, version_minor, version_major))
