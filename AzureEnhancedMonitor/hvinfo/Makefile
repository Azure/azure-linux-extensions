CC := gcc
SRCDIR := src
LIBDIR := lib
INCDIR := include
BUILDDIR := build
TARGET := bin/hvinfo

SRCEXT := c
SOURCES := $(shell find $(SRCDIR) -type f -name *.$(SRCEXT))
OBJECTS := $(patsubst $(SRCDIR)/%,$(BUILDDIR)/%,$(SOURCES:.$(SRCEXT)=.o))
CFLAGS := -g
LDFLAGS := 
INC := -I $(INCDIR)
LIB := -L $(LIBDIR)

all : $(TARGET)

$(TARGET): $(OBJECTS)
	@echo "Linking..."
	$(CC) $^ $(LDFLAGS) -o $(TARGET) $(LIB)

$(BUILDDIR)/%.o: $(SRCDIR)/%.$(SRCEXT)
	@mkdir -p $(BUILDDIR)
	@echo "Compiling..."
	$(CC) $(CFLAGS) $(INC) -c -o $@ $<

clean:
	@echo "Cleaning..."
	$(RM) -r $(BUILDDIR) $(TARGET)

.PHONY: clean test
