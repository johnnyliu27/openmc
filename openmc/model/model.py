from collections.abc import Iterable

import openmc
from openmc.checkvalue import check_type, check_value


class Model(object):
    """Model container.

    This class can be used to store instances of :class:`openmc.Geometry`,
    :class:`openmc.Materials`, :class:`openmc.Settings`,
    :class:`openmc.Tallies`, :class:`openmc.Plots`, and :class:`openmc.CMFD`,
    thus making a complete model. The :meth:`Model.export_to_xml` method will
    export XML files for all attributes that have been set. If the
    :meth:`Model.materials` attribute is not set, it will attempt to create a
    ``materials.xml`` file based on all materials appearing in the geometry.

    Parameters
    ----------
    geometry : openmc.Geometry, optional
        Geometry information
    materials : openmc.Materials, optional
        Materials information
    settings : openmc.Settings, optional
        Settings information
    tallies : openmc.Tallies, optional
        Tallies information
    cmfd : openmc.CMFD, optional
        CMFD information
    plots : openmc.Plots, optional
        Plot information

    Attributes
    ----------
    geometry : openmc.Geometry
        Geometry information
    materials : openmc.Materials
        Materials information
    settings : openmc.Settings
        Settings information
    tallies : openmc.Tallies
        Tallies information
    cmfd : openmc.CMFD
        CMFD information
    plots : openmc.Plots
        Plot information

    """

    def __init__(self, geometry=None, materials=None, settings=None,
                 tallies=None, cmfd=None, plots=None):
        self.geometry = openmc.Geometry()
        self.materials = openmc.Materials()
        self.settings = openmc.Settings()
        self.cmfd = cmfd
        self.tallies = openmc.Tallies()
        self.plots = openmc.Plots()

        if geometry is not None:
            self.geometry = geometry
        if materials is not None:
            self.materials = materials
        if settings is not None:
            self.settings = settings
        if tallies is not None:
            self.tallies = tallies
        if plots is not None:
            self.plots = plots

    @property
    def geometry(self):
        return self._geometry

    @property
    def materials(self):
        return self._materials

    @property
    def settings(self):
        return self._settings

    @property
    def tallies(self):
        return self._tallies

    @property
    def cmfd(self):
        return self._cmfd

    @property
    def plots(self):
        return self._plots

    @geometry.setter
    def geometry(self, geometry):
        check_type('geometry', geometry, openmc.Geometry)
        self._geometry = geometry

    @materials.setter
    def materials(self, materials):
        check_type('materials', materials, Iterable, openmc.Material)
        if isinstance(materials, openmc.Materials):
            self._materials = materials
        else:
            del self._materials[:]
            for mat in materials:
                self._materials.append(mat)

    @settings.setter
    def settings(self, settings):
        check_type('settings', settings, openmc.Settings)
        self._settings = settings

    @tallies.setter
    def tallies(self, tallies):
        check_type('tallies', tallies, Iterable, openmc.Tally)
        if isinstance(tallies, openmc.Tallies):
            self._tallies = tallies
        else:
            del self._tallies[:]
            for tally in tallies:
                self._tallies.append(tally)

    @cmfd.setter
    def cmfd(self, cmfd):
        check_type('cmfd', cmfd, (openmc.CMFD, type(None)))
        self._cmfd = cmfd

    @plots.setter
    def plots(self, plots):
        check_type('plots', plots, Iterable, openmc.Plot)
        if isinstance(plots, openmc.Plots):
            self._plots = plots
        else:
            del self._plots[:]
            for plot in plots:
                self._plots.append(plot)

    def deplete(self, timesteps, power, chain_file=None, method='cecm',
                **kwargs):
        """Deplete model using specified timesteps/power

        Parameters
        ----------
        timesteps : iterable of float
            Array of timesteps in units of [s]. Note that values are not
            cumulative.
        power : float or iterable of float
            Power of the reactor in [W]. A single value indicates that the power
            is constant over all timesteps. An iterable indicates potentially
            different power levels for each timestep. For a 2D problem, the
            power can be given in [W/cm] as long as the "volume" assigned to a
            depletion material is actually an area in [cm^2].
        chain_file : str, optional
            Path to the depletion chain XML file.  Defaults to the
            :envvar:`OPENMC_DEPLETE_CHAIN` environment variable if it exists.
        method : {'cecm', 'predictor'}
             Integration method used for depletion
        **kwargs
            Keyword arguments passed to integration function (e.g.,
            :func:`openmc.deplete.integrator.cecm`)

        """
        # Import the depletion module.  This is done here rather than the module
        # header to delay importing openmc.capi (through openmc.deplete) which
        # can be tough to install properly.
        import openmc.deplete as dep

        # Create OpenMC transport operator
        op = dep.Operator(self.geometry, self.settings, chain_file)

        # Perform depletion
        if method == 'predictor':
            dep.integrator.predictor(op, timesteps, power, **kwargs)
        elif method == 'cecm':
            dep.integrator.cecm(op, timesteps, power, **kwargs)
        else:
            check_value('method', method, ('cecm', 'predictor'))

    def export_to_xml(self):
        """Export model to XML files."""

        self.settings.export_to_xml()
        if not self.settings.dagmc:
            self.geometry.export_to_xml()

        # If a materials collection was specified, export it. Otherwise, look
        # for all materials in the geometry and use that to automatically build
        # a collection.
        if self.materials:
            self.materials.export_to_xml()
        else:
            materials = openmc.Materials(self.geometry.get_all_materials()
                                         .values())
            materials.export_to_xml()

        if self.tallies:
            self.tallies.export_to_xml()
        if self.cmfd is not None:
            self.cmfd.export_to_xml()
        if self.plots:
            self.plots.export_to_xml()

    def run(self, **kwargs):
        """Creates the XML files, runs OpenMC, and returns k-effective

        Parameters
        ----------
        **kwargs
            All keyword arguments are passed to :func:`openmc.run`

        Returns
        -------
        uncertainties.UFloat
            Combined estimator of k-effective from the statepoint

        """
        self.export_to_xml()

        openmc.run(**kwargs)

        n = self.settings.batches
        if self.settings.statepoint is not None:
            if 'batches' in self.settings.statepoint:
                n = self.settings.statepoint['batches'][-1]

        with openmc.StatePoint('statepoint.{}.h5'.format(n)) as sp:
            return sp.k_combined
