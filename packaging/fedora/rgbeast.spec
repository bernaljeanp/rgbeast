%global forgeurl https://github.com/bernaljeanp/rgbeast
# pyproject pide PySide6-Essentials (nombre de pip); Fedora lo da como python3-pyside6.
%global __requires_exclude ^python3(\\.[0-9]+)?dist\\(pyside6-essentials\\)

Name:           rgbeast
Version:        0.1.1
Release:        1%{?dist}
Summary:        Centro de control para portátiles gaming en Linux

License:        GPL-3.0-only
URL:            %{forgeurl}
Source0:        %{forgeurl}/archive/v%{version}/%{name}-%{version}.tar.gz
BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  pyproject-rpm-macros
BuildRequires:  python3-setuptools
BuildRequires:  qt6-qtshadertools
BuildRequires:  systemd-rpm-macros
BuildRequires:  desktop-file-utils

Requires:       python3-pyside6
Requires:       qt6-qtdeclarative
Requires:       qt6-qtsvg
Requires:       python3-gobject
Requires:       systemd
Recommends:     (power-profiles-daemon or tuned-ppd)

%description
RGBEAST reúne en una sola aplicación las temperaturas de CPU y GPU, el control
de ventiladores y sus curvas, los modos de rendimiento, el límite de carga de la
batería, las luces del teclado y los perfiles por juego, usando las interfaces
estándar del kernel. Incluye un servicio mínimo y aislado para las operaciones
que requieren privilegios.

%prep
%autosetup -n %{name}-%{version}

%generate_buildrequires
%pyproject_buildrequires -R

%build
# Shaders compilados con el Qt de la distro.
QSB=%{_bindir}/qsb-qt6 sh tools/build_shaders.sh
%pyproject_wheel

%install
%pyproject_install
%pyproject_save_files rgbeast
sh packaging/install-files.sh %{buildroot} %{_libexecdir}/rgbeast

%check
desktop-file-validate %{buildroot}%{_datadir}/applications/rgbeast.desktop

%post
%systemd_post rgbeast-helper.service
%systemd_user_post rgbeast-agent.service
%{?udev_hwdb_update}

%preun
%systemd_preun rgbeast-helper.service
%systemd_user_preun rgbeast-agent.service

%postun
%systemd_postun_with_restart rgbeast-helper.service
%{?udev_hwdb_update}

%files -f %{pyproject_files}
%license LICENSE
%doc README.md
%{_bindir}/rgbeast
%{_bindir}/rgbeast-agent
%{_libexecdir}/rgbeast/
%{_unitdir}/rgbeast-helper.service
%{_userunitdir}/rgbeast-agent.service
%{_udevhwdbdir}/70-rgbeast-alienware.hwdb
%{_datadir}/dbus-1/system.d/io.github.bernaljeanp.Rgbeast.Helper.conf
%{_datadir}/applications/rgbeast.desktop
%{_datadir}/icons/hicolor/scalable/apps/rgbeast.svg
%{_datadir}/icons/hicolor/scalable/status/rgbeast-symbolic.svg

%changelog
* Wed Nov 11 2026 bernaljeanp <316348178+bernaljeanp@users.noreply.github.com> - 0.1.1-1
- Nuevo nombre: RGBEAST (antes Vórtice) e icono nuevo

* Tue Nov 10 2026 bernaljeanp <316348178+bernaljeanp@users.noreply.github.com> - 0.1.0-1
- Primera versión empaquetada
