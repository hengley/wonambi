from logging import getLogger
from copy import deepcopy

from numpy import asarray, dot, zeros, where, c_, mean
from numpy.linalg import norm

from ..attr import Channels

lg = getLogger(__name__)


class Montage:
    """Apply linear transformation to the channels.

    Parameters
    ----------
    ref_chan : list of str
        list of channels used as reference
    ref_to_avg : bool
        if re-reference to average or not
    bipolar : float
        distance in mm to consider two channels as neighbors and then compute
        the bipolar montage between them.

    Attributes
    ----------

    Notes
    -----

    """
    def __init__(self, ref_chan=None, ref_to_avg=False, bipolar=None):
        if ref_to_avg and ref_chan is not None:
            raise TypeError('You cannot specify reference to the average and '
                            'the channels to use as reference')

        if ref_chan is not None:
            if (not isinstance(ref_chan, (list, tuple)) or
                not all(isinstance(x, str) for x in ref_chan)):
                    raise TypeError('chan should be a list of strings')

        if ref_chan is None:
            ref_chan = []  # TODO: check bool for ref_chan
        self.ref_chan = ref_chan
        self.ref_to_avg = ref_to_avg
        self.bipolar = bipolar

    def __call__(self, data):
        """Apply the montage to the data.

        Parameters
        ----------
        data : instance of DataRaw
            the data to filter

        Returns
        -------
        filtered_data : instance of DataRaw
            filtered data

        """
        if self.bipolar:
            if not data.attr['chan']:
                raise ValueError('Data should have Chan information in attr')

            _assert_equal_channels(data.axis['chan'])
            chan_in_data = data.axis['chan'][0]
            chan = data.attr['chan']
            chan = chan(lambda x: x.label in chan_in_data)
            chan, trans = create_bipolar_chan(chan, self.bipolar)
            data.attr['chan'] = chan

        mdata = deepcopy(data)

        if self.ref_to_avg or self.ref_chan or self.bipolar:

            for i in range(mdata.number_of('trial')):
                if self.ref_to_avg or self.ref_chan:
                    if self.ref_to_avg:
                        self.ref_chan = data.axis['chan'][0]

                    ref_data = mdata(trial=i, chan=self.ref_chan)
                    mdata.data[i] = (mdata(trial=i) -
                                     mean(ref_data,
                                          axis=mdata.index_of('chan')))

                elif self.bipolar:

                    if not data.index_of('chan') == 0:
                        raise ValueError('For matrix multiplication to work, '
                                         'the first dimension should be chan')
                    mdata.data[i] = dot(trans, mdata(trial=i))
                    mdata.axis['chan'][i] = asarray(chan.return_label(),
                                                    dtype='U')

        return mdata


def _assert_equal_channels(axis):
    """check that all the trials have the same channels, in the same order.

    Parameters
    ----------
    axis : ndarray of ndarray
        one of the data axis

    Raises
    ------

    """
    for i0 in axis:
        for i1 in axis:
            if not all(i0 == i1):
                raise ValueError('The channels for all the trials should have '
                                 'the same labels, in the same order.')


def create_bipolar_chan(chan, max_dist):
    chan_dist = zeros((chan.n_chan, chan.n_chan), dtype='bool')
    for i0, chan0 in enumerate(chan.chan):
        for i1, chan1 in enumerate(chan.chan):
            if i0 < i1 and norm(chan0.xyz - chan1.xyz) < max_dist:
                chan_dist[i0, i1] = True

    x_all, y_all = where(chan_dist)

    bipolar_labels = []
    bipolar_xyz = []
    bipolar_trans = []

    for x0, x1 in zip(x_all, y_all):

        new_label = chan.chan[x0].label + '-' + chan.chan[x1].label
        bipolar_labels.append(new_label)

        xyz = mean(c_[chan.chan[x0].xyz, chan.chan[x1].xyz], axis=1)
        bipolar_xyz.append(xyz)

        trans = zeros(chan.n_chan)
        trans[x0] = 1
        trans[x1] = -1
        bipolar_trans.append(trans)

    bipolar_xyz = c_[bipolar_xyz]
    bipolar_trans = c_[bipolar_trans]

    bipolar = Channels(bipolar_labels, bipolar_xyz)

    return bipolar, bipolar_trans
