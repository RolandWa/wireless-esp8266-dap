"""Vendor3 (info) / Vendor4 (select board) message helpers in read_vtarget_tcp.py.

The byte vector below is the same one asserted by the C test
test_encode_info_layout, so the two sides of the protocol cannot drift apart.
"""
import pytest

import read_vtarget_tcp as proto

# C side: min=1326 max=4200 requested=3300 settle=600 ms, board "PCB-05"
VENDOR3_NOT_SETTLED = bytes([
    0x83,
    0x00,
    0x2E, 0x05,
    0x68, 0x10,
    0xE4, 0x0C,
    0x58, 0x02,
    0x06, ord("P"), ord("C"), ord("B"), ord("-"), ord("0"), ord("5"),
])


def test_decode_matches_the_c_encoder_vector():
    info = proto.decode_vtarget_info(VENDOR3_NOT_SETTLED)
    assert info == {
        "settled": False, "min_mv": 1326, "max_mv": 4200, "requested_mv": 3300,
        "settle_ms": 600, "board": "PCB-05",
    }


def test_decode_settled_flag():
    resp = bytearray(VENDOR3_NOT_SETTLED)
    resp[1] = 0x01
    resp[8] = resp[9] = 0
    info = proto.decode_vtarget_info(bytes(resp))
    assert info["settled"] is True and info["settle_ms"] == 0


def test_decode_ignores_trailing_padding():
    info = proto.decode_vtarget_info(VENDOR3_NOT_SETTLED + bytes(40))
    assert info["board"] == "PCB-05"


def test_decode_default_table_name():
    resp = bytes([0x83, 0x01, 0x2E, 0x05, 0x68, 0x10, 0, 0, 0, 0, 7]) + b"CLUSTER"
    assert proto.decode_vtarget_info(resp)["board"] == "CLUSTER"


def test_decode_empty_name():
    resp = bytes([0x83, 0x01, 1, 0, 2, 0, 0, 0, 0, 0, 0])
    assert proto.decode_vtarget_info(resp)["board"] == ""


@pytest.mark.parametrize("resp, message", [
    (b"", "not a Vendor3"),
    (bytes([0x81, 0x00]), "not a Vendor3"),
    (bytes([0x83]), "not a Vendor3"),
    (bytes([0x83, 0x80]), "not supported"),            # unsupported target
    (bytes([0x83, 0x01]), "too short"),                # old firmware: only the command id echoed + flag
    (VENDOR3_NOT_SETTLED[:11], "truncated"),           # name_len=6 but no name bytes
    (VENDOR3_NOT_SETTLED[:14], "truncated"),
])
def test_decode_rejects_malformed_responses(resp, message):
    with pytest.raises(ValueError, match=message):
        proto.decode_vtarget_info(resp)


def test_old_firmware_single_byte_response_is_rejected():
    # Firmware without Vendor3 echoes only the command id
    with pytest.raises(ValueError):
        proto.decode_vtarget_info(bytes([0x83]))


# --------------------------------------------------------------------- Vendor4

def test_build_set_board_request_layout():
    pkt = proto.build_set_board_request("PCB-05")
    assert len(pkt) == proto.DAP_PACKET_SIZE
    assert pkt[:8] == bytes([0x84, 6]) + b"PCB-05"
    assert set(pkt[8:]) == {0}


def test_build_set_board_request_longest_name():
    name = "ABCDEFGHIJKLMNO"           # 15 characters = firmware limit
    pkt = proto.build_set_board_request(name)
    assert pkt[1] == 15 and pkt[2:17] == name.encode()


@pytest.mark.parametrize("bad", ["", "ABCDEFGHIJKLMNOP", "x" * 40])
def test_build_set_board_request_rejects_bad_lengths(bad):
    with pytest.raises(ValueError):
        proto.build_set_board_request(bad)


def test_build_set_board_request_rejects_non_ascii():
    with pytest.raises(UnicodeEncodeError):
        proto.build_set_board_request("PCB-Ż5")


def test_command_ids_are_consecutive_vendor_commands():
    assert (proto.CMD_DAP_VENDOR1, proto.CMD_DAP_VENDOR2,
            proto.CMD_DAP_VENDOR3, proto.CMD_DAP_VENDOR4) == (0x81, 0x82, 0x83, 0x84)
