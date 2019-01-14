import numpy as np
import copy
from numpy import fft
from NuRadioReco.utilities import units
from scipy import signal
from numpy.polynomial import polynomial as poly
import matplotlib.pyplot as plt
from radiotools import helper as hp
from radiotools import coordinatesystems
from NuRadioReco.utilities import fft
import logging
logger = logging.getLogger('stationSignalReconstructor')
from NuRadioReco.framework.parameters import stationParameters as stnp
from NuRadioReco.framework.parameters import electricFieldParameters as efp

class electricFieldSignalReconstructor:
    """
    Calculates basic signal parameters.
    """

    def __init__(self):
        self.__conversion_factor_integrated_signal = 2.65441729 * 1e-3 * 1.e-9 * 6.24150934 * 1e18  # to convert V**2/m**2 * s -> J/m**2 -> eV/m**2
        self.begin()

    def begin(self, signal_window_pre=10 * units.ns, signal_window_post=40 * units.ns, noise_window=100 * units.ns):
        self.__signal_window_pre = signal_window_pre
        self.__signal_window_post = signal_window_post
        self.__noise_window = noise_window

    def run(self, evt, station, det, debug=False):

        for electric_field in station.get_electric_fields():
            trace_copy = copy.copy(electric_field.get_trace())

            # calculate hilbert envelope
            envelope = np.abs(signal.hilbert(trace_copy))
            envelope_mag = np.linalg.norm(envelope, axis=0)
            signal_time_bin = np.argmax(envelope_mag)
            signal_time = signal_time_bin / electric_field.get_sampling_rate()
            electric_field[efp.signal_time] = signal_time

    #
            low_pos = np.int(130 * units.ns * electric_field.get_sampling_rate())
            up_pos = np.int(210 * units.ns * electric_field.get_sampling_rate())
            if(debug):
                fig, ax = plt.subplots(1, 1)
                sc = ax.scatter(trace_copy[1, low_pos:up_pos], trace_copy[2, low_pos:up_pos], c=electric_field.get_times()[low_pos:up_pos], s=5)
                fig.colorbar(sc, ax=ax)
                ax.set_aspect('equal')
                ax.set_xlabel("eTheta")
                ax.set_ylabel("ePhi")
                fig.tight_layout()
    #

            low_pos, up_pos = hp.get_interval(envelope_mag, scale=0.5)
            v_start = trace_copy[:, signal_time_bin]
            v_avg = np.zeros(3)
            for i in range(low_pos, up_pos + 1):
                v = trace_copy[:, i]
                alpha = hp.get_angle(v_start, v)
                if(alpha > 0.5 * np.pi):
                    v *= -1
                v_avg += v
            pole = np.arctan2(np.abs(v_avg[2]), np.abs(v_avg[1]))
    #         if(pole > 180 * units.deg):
    #             pole -= 360 * units.deg
    #         if(pole > 90 * units.deg):
    #             pole = 180 * units.deg - pole
            electric_field[efp.polarization_angle] = pole
            logger.info("average e-field vector = {:.4g}, {:.4g}, {:.4g} -> polarization = {:.1f}deg".format(v_avg[0], v_avg[1], v_avg[2], pole / units.deg))
            trace = electric_field.get_trace()

            if(debug):
                fig, ax = plt.subplots(1, 1)
                tt = electric_field.get_times()
                t0 = electric_field.get_trace_start_time()
                dt = 1. / electric_field.get_sampling_rate()
                ax.plot(tt / units.ns, trace[1] / units.mV * units.m)
                ax.plot(tt / units.ns, trace[2] / units.mV * units.m)
                ax.plot(tt / units.ns, envelope_mag / units.mV * units.m)
                ax.vlines([low_pos * dt + t0, up_pos * dt + t0], 0, envelope_mag.max() / units.mV * units.m)
                ax.vlines([signal_time - self.__signal_window_pre + t0, signal_time + self.__signal_window_post + t0], 0, envelope_mag.max() / units.mV * units.m, linestyles='dashed')

            t0 = electric_field.get_trace_start_time()
            times = electric_field.get_times()
            mask_signal_window = (times > (signal_time - self.__signal_window_pre + t0)) & (times < (signal_time + self.__signal_window_post + t0))
            mask_noise_window = np.zeros_like(mask_signal_window, dtype=np.bool)
            if(self.__noise_window > 0):
                mask_noise_window[np.int(np.round((-self.__noise_window - 141.) * electric_field.get_sampling_rate())):np.int(np.round(-141. * electric_field.get_sampling_rate()))] = np.ones(np.int(np.round(self.__noise_window * electric_field.get_sampling_rate())), dtype=np.bool)  # the last n bins

            dt = times[1] - times[0]
            f_signal = np.sum(trace[:, mask_signal_window] ** 2, axis=1) * dt
            signal_energy_fluence = f_signal
            logger.debug('f signal {}'.format(f_signal))
            f_noise = np.zeros_like(f_signal)
            signal_energy_fluence_error = np.zeros(3)
            if(np.sum(mask_noise_window)):
                f_noise = np.sum(trace[:, mask_noise_window] ** 2, axis=1) * dt
                logger.debug('f_noise {},  {}/{} = {}'.format(f_noise * np.sum(mask_signal_window) / np.sum(mask_noise_window), np.sum(mask_signal_window), np.sum(mask_noise_window), 1. * np.sum(mask_signal_window) / np.sum(mask_noise_window)))
                signal_energy_fluence = f_signal - f_noise * np.sum(mask_signal_window) / np.sum(mask_noise_window)
                RMSNoise = np.sqrt(np.mean(trace[:, mask_noise_window] ** 2, axis=1))
                signal_energy_fluence_error = (4 * np.abs(signal_energy_fluence) * RMSNoise ** 2 * dt + 2 * (self.__signal_window_pre + self.__signal_window_post) * RMSNoise ** 4 * dt) ** 0.5

            signal_energy_fluence *= self.__conversion_factor_integrated_signal
            signal_energy_fluence_error *= self.__conversion_factor_integrated_signal
            electric_field.set_parameter(efp.signal_energy_fluence, signal_energy_fluence)
            electric_field.set_parameter_error(efp.signal_energy_fluence, signal_energy_fluence_error)

            logger.info("f = {} +- {}".format(signal_energy_fluence / units.eV * units.m2, signal_energy_fluence_error / units.eV * units.m2))

            # calculate polarization angle from energy fluence
            x = np.abs(signal_energy_fluence[1]) ** 0.5
            y = np.abs(signal_energy_fluence[2]) ** 0.5
            sx = signal_energy_fluence_error[1] * 0.5
            sy = signal_energy_fluence_error[2] * 0.5
            pol_angle = np.arctan2(y, x)
            pol_angle_error = 1. / (x ** 2 + y ** 2) * (y ** 2 * sx ** 2 + x ** 2 * sy ** 2) ** 0.5  # gaussian error propagation
            logger.info("polarization angle = {:.1f} +- {:.1f}".format(pol_angle / units.deg, pol_angle_error / units.deg))
            electric_field.set_parameter(efp.polarization_angle, pol_angle)
            electric_field.set_parameter_error(efp.polarization_angle, pol_angle_error)

            # compute expeted polarization
            site = det.get_site(station.get_id())
            exp_efield = hp.get_lorentzforce_vector(electric_field[efp.zenith], electric_field[efp.azimuth], hp.get_magnetic_field_vector(site))
            cs = coordinatesystems.cstrafo(electric_field[efp.zenith], electric_field[efp.azimuth], site=site)
            exp_efield_onsky = cs.transform_from_ground_to_onsky(exp_efield)
            exp_pol_angle = np.arctan2(np.abs(exp_efield_onsky[2]), np.abs(exp_efield_onsky[1]))
            logger.info("expected polarization angle = {:.1f}".format(exp_pol_angle / units.deg))
            electric_field.set_parameter(efp.polarization_angle_expectation, exp_pol_angle)

            return

    def end(self):
        pass