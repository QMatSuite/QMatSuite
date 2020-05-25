/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or
 *     any later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package com.consts;

import java.util.HashMap;

public interface QeDocumentation {
	HashMap<String, String> pwDoc  = new HashMap<String, String>() {/**
		 * 
		 */
		private static final long serialVersionUID = 2857832825173277356L;

	{
	    put("infoRestart", " restart_mode, Default: 'from_scratch'\r\n"
	    		+ "Available options are:\r\n" + 
	    		"'from_scratch' :\r\n" + 
	    		"From scratch. This is the normal way to perform a PWscf calculation\r\n" + 
	    		"'restart' :\r\n" + 
	    		"From previous interrupted run. Use this switch only if you want to "
	    		+ "continue an interrupted calculation, not to start a new one, or to " + 
	    		"perform non-scf calculations.  Works only if the calculation was " + 
	    		"cleanly stopped using variable max_seconds, or by user request " + 
	    		"with an \"exit file\" (i.e.: create a file \"prefix\".EXIT, in directory " + 
	    		"\"outdir\"; see variables prefix, outdir).  Overrides startingwfc " + 
	    		"and startingpot.");
	    put("infoForce", "calculate forces. It is set to .TRUE. automatically if " + 
	    		"calculation == 'relax','md','vc-md'");
	}};
	HashMap<String, String> pwShortDoc  = new HashMap<String, String>() {/**
		 * 
		 */
		private static final long serialVersionUID = 8728169068537886008L;

	{
	    put("infoRestart", "restart mode");
	    put("infoForce", "whether or not calculate forces");
	}};
}
