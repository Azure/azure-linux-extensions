%define      debug_package %{nil}

Name:        PACKAGE
Version:     VERSION
Release:     LABEL
Summary:     Azure MDS daemon for Linux Diagnostic Extension

Group:       Productivity/Security
License:     MIT
URL:         www.microsoft.com
Source0:     %{name}-%{version}.tgz
BuildRoot:   %{_tmppath}/%{name}-%{version}-%{release}-buildroot

Requires:    scx, omi, omsagent

%description
%{summary}

%prep
%setup -q

%build
# Empty section

%install
cp -a . %{buildroot}

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/usr/local/lad/bin/mdsd
/usr/share/doc/lad-mdsd/ChangeLog

%changelog

