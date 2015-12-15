#!/usr/bin/python3
# -*- coding: utf-8 -*-

from __future__ import (
    unicode_literals,
    absolute_import,
    print_function,
    division)
import io
import time
import picamera
import numpy as np


def capture_image(stream, camera):
    camera.capture(stream, format='jpeg', bayer=True)

    # Extract the raw Bayer data from the end of the stream, check the
    # header and strip if off before converting the data into a numpy array

    data = stream.getvalue()[-6404096:]
    assert data[:4] == b'BRCM'
    data = data[32768:]
    data = np.fromstring(data, dtype=np.uint8)

    # The data consists of 1952 rows of 3264 bytes of data. The last 8 rows
    # of data are unused (they only exist because the actual resolution of
    # 1944 rows is rounded up to the nearest 16). Likewise, the last 24
    # bytes of each row are unused (why?). Here we reshape the data and
    # strip off the unused bytes

    data = data.reshape((1952, 3264))[:1944, :3240]

    # Horizontally, each row consists of 2592 10-bit values. Every four
    # bytes are the high 8-bits of four values, and the 5th byte contains
    # the packed low 2-bits of the preceding four values. In other words,
    # the bits of the values A, B, C, D and arranged like so:
    #
    #  byte 1   byte 2   byte 3   byte 4   byte 5
    # AAAAAAAA BBBBBBBB CCCCCCCC DDDDDDDD AABBCCDD
    #
    # Here, we convert our data into a 16-bit array, shift all values left
    # by 2-bits and unpack the low-order bits from every 5th byte in each
    # row, then remove the columns containing the packed bits

    data = data.astype(np.uint16) << 2
    for byte in range(4):
        data[:, byte::5] |= ((data[:, 4::5] >> ((4 - byte) * 2)) & 0b11)
    data = np.delete(data, np.s_[4::5], 1)

    # Now to split the data up into its red, green, and blue components. The
    # Bayer pattern of the OV5647 sensor is BGGR. In other words the first
    # row contains alternating green/blue elements, the second row contains
    # alternating red/green elements, and so on as illustrated below:
    #
    # GBGBGBGBGBGBGB
    # RGRGRGRGRGRGRG
    # GBGBGBGBGBGBGB
    # RGRGRGRGRGRGRG
    #
    # Please note that if you use vflip or hflip to change the orientation
    # of the capture, you must flip the Bayer pattern accordingly

    rgb = np.zeros(data.shape + (3,), dtype=data.dtype)
    rgb[1::2, 0::2, 0] = data[1::2, 0::2]  # Red
    rgb[0::2, 0::2, 1] = data[0::2, 0::2]  # Green
    rgb[1::2, 1::2, 1] = data[1::2, 1::2]  # Green
    rgb[0::2, 1::2, 2] = data[0::2, 1::2]  # Blue

    return rgb


if __name__ == '__main__':
    stream = io.BytesIO()
    pixels = [(1000, 1500, 1), (1002, 1500, 1), (1004, 1500, 1), (1006, 1500, 1)]
    histograms = [[0] * 1024] * len(pixels)
    with picamera.PiCamera() as camera:
        # Let the camera warm up for a couple of seconds
        time.sleep(2)

        for i in range(10):
            # Capture the image, including the Bayer data
            rgb = capture_image(stream, camera)
            for j, p in enumerate(pixels):
                histograms[j][rgb[p[0], p[1], p[2]]] += 1
    for histogram in histograms:
        print(", ".join([str(x) for x in histogram]))

