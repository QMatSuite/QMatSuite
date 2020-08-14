/*******************************************************************************
 * Copyright (c) 2020 Haonan Huang.
 *
 *     This file is part of QuantumVITAS (Quantum Visualization Interactive 
 *     Toolkit for Ab-initio Simulations).
 *
 *     QuantumVITAS is free software: you can redistribute it and/or modify
 *     it under the terms of the GNU General Public License as published by
 *     the Free Software Foundation, either version 3 of the License, or any 
 *     later version.
 *
 *     QuantumVITAS is distributed in the hope that it will be useful,
 *     but WITHOUT ANY WARRANTY; without even the implied warranty of
 *     MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *     GNU General Public License for more details.
 *
 *     You should have received a copy of the GNU General Public License
 *     along with QuantumVITAS.  If not, see <https://www.gnu.org/licenses/gpl-3.0.txt>.
 *******************************************************************************/
package app.centerwindow;


import core.app.centerwindow.OutputViewerController;
import core.app.input.InputGeoController;
import core.main.MainClass;


public class OutputViewerControllerCP2K extends OutputViewerController{
    
    		
    public OutputViewerControllerCP2K(MainClass mc, InputGeoController contGeo){
    	super(mc,contGeo);
    	
	}

	@Override
	protected void updateComboAnalysis() {
		// TODO Auto-generated method stub
		
	}

	@Override
	protected void getFileCategory(String newTab) {
		// TODO Auto-generated method stub
		
	}

	@Override
	protected boolean loadFile() {
		// TODO Auto-generated method stub
		return false;
	}

	@Override
	protected void updateIoDisplay() {
		// TODO Auto-generated method stub
		
	}

	@Override
	protected boolean isFileImportant(String item) {
		// TODO Auto-generated method stub
		return false;
	}
	

}
