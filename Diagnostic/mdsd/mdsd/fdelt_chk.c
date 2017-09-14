/*
   Copyright (c) Microsoft Corporation. All rights reserved.
   Licensed under the MIT license.
*/

#include <sys/select.h>

# define strong_alias(name, aliasname) _strong_alias(name, aliasname)
# define _strong_alias(name, aliasname) \
  extern __typeof (name) aliasname __attribute__ ((alias (#name)));

/*
 * 'unsigned' dropped from the original source, to match
 * the prototype defined in select2.h.
 */
long int
__fdelt_chk (long int d)
{
  if (d >= FD_SETSIZE)
    __chk_fail ();

  return d / __NFDBITS;
}
strong_alias (__fdelt_chk, __fdelt_warn)
