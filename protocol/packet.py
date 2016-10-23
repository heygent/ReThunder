from protocol.packet_fields import DataField, FlagField
from functools import partial


class Packet:

    def __init__(self):

        self.heading_frame = 0
        self.source_static_frame = 0
        self.source_dynamic_frame = 0
        self.destination_frame = 0
        self.payload_length_frame = 0

        self.noise_table = {}
        self.payload = None
        self.errors = 0

    __HeadingDataField = partial(DataField, 'heading_frame')
    __HeadingFlagField = partial(FlagField, 'heading_frame')
    __FullFrameField   = partial(DataField, roffset=0, length=11)

    version     = __HeadingDataField(9, 2)
    ack         = __HeadingFlagField(8)
    response    = __HeadingFlagField(7)
    code        = __HeadingDataField(3, 4)
    token       = __HeadingDataField(0, 3)

    source_static   = __FullFrameField('source_static_frame')
    source_dynamic  = __FullFrameField('source_dynamic_frame')
    destination     = __FullFrameField('destination_frame')
    payload_length  = __FullFrameField('payload_length_frame')
    new_static_addr = __FullFrameField('payload_length_frame')
