## 1.5.10 (2020-09-09)
- VMAccess Linux is now more robust to the absence of ovf-env.xml file

## 1.5.6 - 1.5.9
- several bug-fixes

## 1.5.5 (2020-07-20)
- Created new python modules under Utils that are meant to be python 3
  compatible and are supposed to be used instead of importing waagent python file through waagentloader.py
- Fixed code injection vulnerability through the username

## 1.5.1 (2018-10-31)
- Support for Python3. Changing VMAccess to work for both Python 2 and Python 3 
  interpreter.

## 1.4.6.0 (2016-09-16)
- Forcibly reset ChallengeAuthenticationResponse to no.  This value was inadvertently set
  in previous releases, and is forcibly reset.

## 1.4.5.0 (2016-09-07)
- Check for None before checking the length of a user's password.  This is
  fallout from allowing and rejecting empty passwords.

## 1.4.4.0 (2016-09-06)
- Do not set ChallengeResponseAuthenticaiton.  This value should not
  be changed by VMAccess.

## 1.4.3.0 (2016-09-05)
- Reject zero length passwords.

## 1.4.2.0 (2016-08-25)
- Ensure expiration (if specified) is used when creating an account
- Backup sshd_config before any edits are made.
- Ensure sshd_config is restarted when edits are made.

## 1.4.1.0 (2016-07-27)
- Install operation posts incorrect status [#206]
- Misspelling of resources/debian_default
