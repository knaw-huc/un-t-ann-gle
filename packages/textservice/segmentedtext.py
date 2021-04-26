# For large lists, consider implementation on basis of blist (pip install blist). This is supposed
# to have performance O(log n) instead of O(n) for insert operations.

import uuid
from functools import total_ordering
from json import JSONEncoder
from abc import ABCMeta, abstractmethod

@total_ordering
class Anchor:
    def __init__(self, identifier, sequence_number):
        self.identifier = identifier
        self.sequence_number = sequence_number # used to compare anchors in their SegmentedText context
            
    def __eq__(self, other):
        return self.sequence_number == other.sequence_number
    
    def __lt__(self, other):
        return self.sequence_number < other.sequence_number
    
    def __repr__(self):
        return str(self.identifier)
        
    def __str__(self):
        return str(self.identifier)
        
class AnchorEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__         

class SegmentedText(metaclass=ABCMeta):
    @abstractmethod
    def append(self, text_element):
        pass
        
    @abstractmethod
    def extend(self, textelement_list):
        pass
        
    @abstractmethod
    def len(self):
        pass
        
    @abstractmethod
    def element_at(self, anchor):
        pass
        
    @abstractmethod
    def slice(self, from_anchor, to_anchor):
        pass
 
    @abstractmethod
    def slice_grid(self, from_anchor, to_anchor):
        pass
       
    @abstractmethod
    def __repr__(self):
        pass
        
    @abstractmethod
    def __str__(self):
        pass
    
class SplittableSegmentedText(SegmentedText):    
    def __init__(self, resource_id=None, begin_offset_in_resource=None, end_offset_in_resource=None):
        self.resource_id = resource_id
        self.text_grid_spec = {'begin_offset_in_resource':begin_offset_in_resource, \
        		'end_offset_in_resource':end_offset_in_resource, 'anchor_type':'anchor_obj'}
        self._ordered_segments = []
        self._anchors = []
        
    # secondary constructor
    @classmethod
    def from_json(cls, json_data):
        instance = cls()
        instance._initialize_from_json(json_data)
        return instance
     
    def append(self, text_element):        
     #   self._anchors[self._new_anchor_id()] = len(self._ordered_segments)
        self._anchors.append(Anchor(self._new_anchor_id(), len(self._anchors)))
        self._ordered_segments.append(text_element)
        return
        
    def extend(self, textelement_list):
        if isinstance(textelement_list, list):
            # add a number of new text segment to self
            for te in textelement_list:
                self.append(te)
        else:
            # textelement_list is a SegmentedText object
            self._ordered_segments.extend(textelement_list._ordered_segments)
            self._anchors.extend(textelement_list._anchors)
        return
    
    def len(self):
        return len(self._ordered_segments)
        
    def element_at(self, anchor):
        if isinstance(anchor, str):
        	anchor = self._get_anchor_by_id(anchor)   
        # return self._ordered_segments[self._anchors[anchor]]
        return self._ordered_segments[self._anchors.index(anchor)]
    
    # so far, only one variation of slicing is supported, add other flavours as well (search for sample code)
    # remark: may go wrong at end of lists, not tested yet
    def slice(self, from_anchor, to_anchor):
        if isinstance(from_anchor, str):
        	from_anchor = self._get_anchor_by_id(from_anchor)
        if isinstance(to_anchor, str):
        	to_anchor = self._get_anchor_by_id(to_anchor)        
        from_index = self._anchors.index(from_anchor)
        to_index = self._anchors.index(to_anchor)
        return self._ordered_segments[from_index:to_index+1]

    def slice_grid(self, from_anchor, to_anchor):
        if isinstance(from_anchor, str):
            	from_anchor = self._get_anchor_by_id(from_anchor)
        if isinstance(to_anchor, str):
            	to_anchor = self._get_anchor_by_id(to_anchor)        
        from_index = self._anchors.index(from_anchor)
        to_index = self._anchors.index(to_anchor)
        
        st_slice = SplittableSegmentedText(self.resource_id, from_anchor, to_anchor)
        st_slice._ordered_segments = self._ordered_segments[from_index:to_index+1]
        st_slice._anchors = self._anchors[from_index:to_index+2]
        
        return st_slice
            
    # remark: split a list element is potentially an expensive operation: the complete list might be recreated.
    def split(self, after_anchor, at_char_offset):
        index_at_after_anchor = self._anchors.index(after_anchor)
        text_to_split = self._ordered_segments[index_at_after_anchor]

        t1 = text_to_split[:at_char_offset]
        t2 = text_to_split[at_char_offset:]

        self._ordered_segments[index_at_after_anchor] = t1
        self._ordered_segments.insert(index_at_after_anchor + 1, t2)

        # determine sequence_number: should be a homogeneously increasing series. Use float value
        # between the sequence_numbers of this anchor and the next one (if it exists)
        
        sn1 = after_anchor.sequence_number
        sn2 = self._anchors[index_at_after_anchor + 1].sequence_number
        
        new_anchor = Anchor(self._new_anchor_id(), (sn1+sn2)/2)
        self._anchors.insert(index_at_after_anchor + 1, new_anchor)
        
        return new_anchor
        
    def _initialize_from_json(self, json_data):
        self.resource_id = json_data['resource_id']
        self._ordered_segments = json_data['_ordered_segments']
        
        if 'text_grid_spec' in json_data:
        	self.text_grid_spec = json_data['text_grid_spec']
        else:
        	self.text_grid_spec = {'begin_offset_in_resource':None, \
        		'end_offset_in_resource':None, 'anchor_type':'anchor_obj'}
        
        for a in json_data['_anchors']:
        	anchor = Anchor(a['identifier'], a['sequence_number'])
        	self._anchors.append(anchor)
    
    def _new_anchor_id(self):
        return 'anchor_' + str(uuid.uuid4())
        
    def _get_anchor_by_id(self, anchor_id):
        return [a for a in self._anchors if a.identifier == anchor_id][0]
        
    def __repr__(self):
        return str(self._anchors)
        
    def __str__(self):
        return str(self._ordered_segments)
        
class SegmentEncoder(JSONEncoder):
    def default(self, o):
        return o.__dict__ 
        
class IndexedSegmentedText(SegmentedText):    
    def __init__(self, resource_id=None, begin_offset_in_resource=None, end_offset_in_resource=None):
        self.resource_id = resource_id
        self.text_grid_spec = {'begin_offset_in_resource':begin_offset_in_resource, \
        		'end_offset_in_resource':end_offset_in_resource, 'anchor_type':'index_int'}
        self._ordered_segments = []
        
    # secondary constructor
    @classmethod
    def from_json(cls, json_data):
        instance = cls()
        instance._initialize_from_json(json_data)
        return instance
                
    def append(self, text_element):        
        self._ordered_segments.append(text_element)
        return
        
    def extend(self, textelement_list):
        self._ordered_segments.extend(textelement_list._ordered_segments)
        return
    
    def len(self):
        return len(self._ordered_segments)
        
    def element_at(self, index):
        return self._ordered_segments[index]
    
    # so far, only one variation of slicing is supported, add other flavours as well (search for sample code)
    # remark: may go wrong at end of lists, not tested yet
    def slice(self, from_index, to_index):
        return self._ordered_segments[from_index:to_index+1]

    def slice_grid(self, from_index, to_index):
        st_slice = IndexedSegmentedText(self.resource_id, from_index, to_index)
        st_slice._ordered_segments = self._ordered_segments[from_index:to_index+1]
        
        return st_slice
        
    def _initialize_from_json(self, json_data):
        self.resource_id = json_data['resource_id']
        self._ordered_segments = json_data['_ordered_segments']
        if 'text_grid_spec' in json_data:
        	self.text_grid_spec = json_data['text_grid_spec']
        else:
        	self.text_grid_spec = {'begin_offset_in_resource':None, \
        		'end_offset_in_resource':None, 'anchor_type':'index_int'}
               
    def __repr__(self):
        return str(self._ordered_segments)
        
    def __str__(self):
        return str(self._ordered_segments)
        