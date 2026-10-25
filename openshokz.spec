Name:           openshokz
Version:        0.1.0
Release:        1%{?dist}
Summary:        Configuration tool for Shokz Bluetooth headsets

License:        GPL-3.0-or-later
URL:            https://github.com/jfenal/openshokz
Source0:        %{name}-%{version}.tar.gz

BuildArch:      noarch

BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
BuildRequires:  python3-pyyaml

Requires:       python3-pyyaml
Requires:       bluez

%description
openshokz is a command-line and graphical configuration tool for Shokz
Bluetooth headsets. It allows switching EQ presets, setting voice prompt
language, and querying device information via the Shokz Serial Port Profile.

%package app
Summary:        GTK4 settings GUI for openshokz
Requires:       %{name} = %{version}-%{release}
Requires:       python3-gobject
Requires:       python3-cairo
Requires:       gtk4
Requires:       libadwaita

%description app
Graphical settings application for openshokz built with GTK4 and Adwaita.
Provides EQ preset switching, language selection, and device information.

%package gnome-extension
Summary:        GNOME Shell quick-settings extension for openshokz
Requires:       %{name} = %{version}-%{release}
Requires:       gnome-shell >= 45

%description gnome-extension
GNOME Shell extension that adds an OpenShokz tile to the Quick Settings panel
for switching EQ presets directly from the system status area.

%prep
%autosetup -n %{name}-%{version}

%build
%py3_build

%install
%py3_install

# Desktop file
install -Dm644 src/openshokz/data/openshokz.desktop \
    %{buildroot}%{_datadir}/applications/openshokz.desktop

# GNOME Shell extension
EXT_UUID="openshokz@jfenal.github.com"
EXT_DIR=%{buildroot}%{_datadir}/gnome-shell/extensions/${EXT_UUID}
install -d ${EXT_DIR}
install -m644 gnome-extension/*.js gnome-extension/metadata.json \
    gnome-extension/stylesheet.css ${EXT_DIR}/

%files
%doc README.md
%{python3_sitelib}/openshokz/
%{python3_sitelib}/openshokz-*.egg-info/
%{_bindir}/openshokz
%{_bindir}/shokz-probe
# Exclude app entry point from base package
%exclude %{_bindir}/openshokz-app

%files app
%{_bindir}/openshokz-app
%{_datadir}/applications/openshokz.desktop

%files gnome-extension
%{_datadir}/gnome-shell/extensions/openshokz@jfenal.github.com/

%changelog
* Sun Oct 26 2026 Jérôme Fenal <jfenal@redhat.com> - 0.1.0-1
- Initial package
